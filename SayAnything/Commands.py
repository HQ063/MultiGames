import json
import logging as log
import datetime
#import ast
import jsonpickle
import os
import psycopg2
import urllib.parse
import sys
from time import sleep

import SayAnything.Controller as SayAnythingController
import Commands

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, ForceReply

import MainController
import GamesController
from Constants.Config import STATS
from SayAnything.Boardgamebox.Board import Board
from SayAnything.Boardgamebox.Game import Game
from SayAnything.Boardgamebox.Player import Player
from Boardgamebox.State import State

from Constants.Config import ADMIN

from Utils.helpers import helper

from collections import namedtuple

from PIL import Image
from io import BytesIO

# Objetos que uso de prueba estaran en el state
from Constants.Cards import cartas_aventura
from Constants.Cards import opciones_opcional
from Constants.Cards import opciones_choose_posible_role
from Constants.Cards import modos_juego

from Constants.Config import JUEGOS_DISPONIBLES
from Constants.Config import MODULOS_DISPONIBES
from Constants.Config import HOJAS_AYUDA

from Constants.Cards import comandos
import random
import re
# Objetos que uso de prueba estaran en el state

# Enable logging

log.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=log.INFO)
logger = log.getLogger(__name__)

#DB Connection I made a Haroku Postgres database first
urllib.parse.uses_netloc.append("postgres")
url = urllib.parse.urlparse(os.environ["DATABASE_URL"])

conn = psycopg2.connect(
    database=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
	
def command_votes(bot, update):
	try:
		#Send message of executing command   
		cid = update.message.chat_id
		#bot.send_message(cid, "Looking for history...")
		#Check if there is a current game 
		if cid in GamesController.games.keys():
			game = GamesController.games.get(cid, None)
			if not game.dateinitvote:
				# If date of init vote is null, then the voting didnt start          
				bot.send_message(cid, "The voting didn't start yet.")
			else:
				#If there is a time, compare it and send history of votes.
				start = game.dateinitvote
				stop = datetime.datetime.now()
				elapsed = stop - start
				if elapsed > datetime.timedelta(minutes=1):
					history_text = "Vote history for President %s and Chancellor %s:\n\n" % (game.board.state.nominated_president.name, game.board.state.nominated_chancellor.name)
					for player in game.player_sequence:
						# If the player is in the last_votes (He voted), mark him as he registered a vote
						if player.uid in game.board.state.last_votes:
							history_text += "%s ha dado pista.\n" % (game.playerlist[player.uid].name)
						else:
							history_text += "%s *no* ha dado pista.\n" % (game.playerlist[player.uid].name)
					bot.send_message(cid, history_text, ParseMode.MARKDOWN)
					
				else:
					bot.send_message(cid, "Five minutes must pass to see the votes") 
		else:
			bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
	except Exception as e:
		bot.send_message(cid, str(e))

		
def command_call(bot, game):
	try:
		# Verifico en mi maquina de estados que comando deberia usar para el estado(fase) actual
		if game.board.state.fase_actual == "Proponiendo Pistas":
			call_proponiendo_pistas(bot, game)
		elif game.board.state.fase_actual == "Revisando Pistas":
			reviewer_player = game.board.state.reviewer_player
			bot.send_message(game.cid, "Revisor {0} recorda que tenes que verificar las pistas".format(helper.player_call(reviewer_player)), ParseMode.MARKDOWN)
		elif game.board.state.fase_actual == "Adivinando":
			active_player = game.board.state.active_player
			bot.send_message(game.cid, "{0} estamos esperando para que hagas /guess EJEMPLO o /pass".format(helper.player_call(active_player)), ParseMode.MARKDOWN)
	except Exception as e:
		bot.send_message(game.cid, str(e))

def call_proponiendo_pistas(bot, game):
	if not game.dateinitvote:
		# If date of init vote is null, then the voting didnt start          
		bot.send_message(game.cid, "No es momento de dar pista.")
	else:
		#If there is a time, compare it and send history of votes.
		start = game.dateinitvote
		stop = datetime.datetime.now()          
		elapsed = stop - start
		if elapsed > datetime.timedelta(minutes=1):
			# Only remember to vote to players that are still in the game
			history_text = ""
			for player in game.player_sequence:
				# If the player is not in last_votes send him reminder
				if player.uid not in game.board.state.last_votes and player.uid != game.board.state.active_player.uid:
					history_text += "Tienes que dar una pista {0}.\n".format(helper.player_call(player))
					# Envio mensaje inicial de pistas para recordarle al jugador la pista y el grupo
					mensaje = "Palabra en el grupo *{1}*.\nJugador activo: *{2}*\nLa frase es: *{0}*, propone tu pista!".format(game.board.state.acciones_carta_actual, game.groupName, game.board.state.active_player.name)
					bot.send_message(player.uid, mensaje, ParseMode.MARKDOWN)
					mensaje = "/resp Ejemplo" if game.board.num_players != 3 else "/prop Ejemplo Ejemplo2"
					bot.send_message(player.uid, mensaje)
			bot.send_message(game.cid, history_text, ParseMode.MARKDOWN)
			if game.board.num_players != 3 and len(game.board.state.last_votes) == len(game.player_sequence)-1:
				SayAnythingController.send_prop(bot, game)
			elif len(game.board.state.last_votes) == len(game.player_sequence)+1:
				# De a 3 jugadores exigo que pongan 2 pistas cada uno son 4 de a 3 jugadores
				SayAnythingController.send_prop(bot, game)
		else:
			bot.send_message(game.cid, "5 minutos deben pasar para llamar a call") 
		
# Cada juego que tenga posibles muchos juegos cuyo dato se ponga en privado tendran que hacer un metodo diferente.
# Le paso user data para que pueda poner su propuesta sin temer 
def command_propose(bot, update, args, user_data):
	try:
		cid = update.message.chat_id
		uid = update.message.from_user.id
		if len(args) > 0:
			# Obtengo todos los juegos de base de datos de los que usan clue
			mensaje_error = ""
			
			games_tipo = MainController.getGamesByTipo('SayAnything')
			
			btns = []
			user_data[uid] = ' '.join(args)
			
			for game_chat_id, game in games_tipo.items():
				if uid in game.playerlist and game.board != None:
					if uid != game.board.state.active_player.uid and game.board.state.fase_actual == "Proponiendo Pistas":
						clue_text = 'prop'
						# Pongo en cid el id del juego actual, para el caso de que haya solo 1
						cid = game_chat_id
						# Creo el boton el cual eligirá el jugador
						txtBoton = game.groupName
						comando_callback = "choosegamepropSA"
						datos = str(game_chat_id) + "*" + comando_callback + "*" + clue_text + "*" + str(uid)
						btns.append([InlineKeyboardButton(txtBoton, callback_data=datos)])				
			if len(btns) != 0:
				if len(btns) == 0:
					#Si es solo 1 juego lo hago automatico
					game = Commands.get_game(cid)
					add_propose(bot, game, uid, propuesta)
				else:
					txtBoton = "Cancel"
					datos = "-1*choosegameclue*" + "prop" + "*" + str(uid)
					btns.append([InlineKeyboardButton(txtBoton, callback_data=datos)])
					btnMarkup = InlineKeyboardMarkup(btns)
					bot.send_message(uid, "En cual de estos grupos queres mandar la pista?", reply_markup=btnMarkup)
			else:
				mensaje_error = "No hay partidas en las que puedas hacer /resp"
				bot.send_message(uid, mensaje_error)
	except Exception as e:
		bot.send_message(uid, str(e))
		log.error("Unknown error: " + str(e))

def callback_choose_game_prop(bot, update, user_data):
	callback = update.callback_query
	log.info('callback_choose_game_prop called: %s' % callback.data)	
	regex = re.search("(-[0-9]*)\*choosegamepropSA\*(.*)\*([0-9]*)", callback.data)
	cid, strcid, opcion, uid, struid = int(regex.group(1)), regex.group(1), regex.group(2), int(regex.group(3)), regex.group(3)	
	
	if cid == -1:
		bot.edit_message_text("Cancelado", uid, callback.message.message_id)
		return	
	game = Commands.get_game(cid)
	mensaje_edit = "Has elegido el grupo {0}".format(game.groupName)	
	bot.edit_message_text(mensaje_edit, uid, callback.message.message_id)	
	propuesta = user_data[uid]	
	# Obtengo el juego y le agrego la pista
	add_propose(bot, game, uid, propuesta)

def add_propose(bot, game, uid, propuesta):
	# Se verifica igual en caso de que quede una botonera perdida
	if uid in game.playerlist:
		#Check if there is a current game
		if game.board == None:
			bot.send_message(game.cid, "El juego no ha comenzado!")
			return					
		if uid == ADMIN[0] or (uid != game.board.state.active_player.uid and game.board.state.fase_actual == "Proponiendo Pistas"):	
			bot.send_message(uid, "Tu pista: %s fue agregada a las pistas." % (propuesta))			
			game.board.state.last_votes[uid] = propuesta
			Commands.save(bot, game.cid)			
			# Verifico si todos los jugadores -1 pusieron pista
			bot.send_message(game.cid, "El jugador *%s* ha puesto una pista." % game.playerlist[uid].name, ParseMode.MARKDOWN)			
			# Todo cambiar a -1 cuando termine las pruebas
			if len(game.board.state.last_votes) == len(game.player_sequence)-1:
				SayAnythingController.send_prop(bot, game)			
		else:
			bot.send_message(uid, "No puedes proponer si sos el jugador activo o ya ha pasado la fase de poner pistas.")
	else:
		bot.send_message(uid, "No puedes hacer clue si no estas en el partido.")
	
	
def command_forced_clue(bot, update):
	uid = update.message.from_user.id	
	cid = update.message.chat_id
	game = get_game(cid)
	'''
	answer = "Pista "
	i = 1
	for uid in game.playerlist:
		if uid != game.board.state.active_player.uid:
			game.board.state.last_votes[uid] = answer + str(i)
			i += 1
	'''
	#game.board.state.reviewer_player = game.playerlist[387393551]
	SayAnythingController.review_clues(bot, game)
		

def command_next_turn(bot, update):
	uid = update.message.from_user.id
	cid = update.message.chat_id
	game = Commands.get_game(cid)	
	SayAnythingController.start_next_round(bot, game)

def command_pass(bot, update):
	log.info('command_pass called')
	uid = update.message.from_user.id
	cid = update.message.chat_id
	game = Commands.get_game(cid)
	
	if game.board.state.fase_actual != "Adivinando" or uid != game.board.state.active_player.uid:
		bot.send_message(game.cid, "No es el momento de adivinar o no eres el que tiene que adivinar", ParseMode.MARKDOWN)
		return
	SayAnythingController.pass_say_anything(bot, game)

def command_pick(bot, update, args):
	try:
		log.info('command_pick called')
		#Send message of executing command   
		cid = update.message.chat_id
		uid = update.message.from_user.id
		game = Commands.get_game(cid)			
		
		if (len(args) < 1 or game.board.state.fase_actual != "Adivinando" 
		    		or uid != game.board.state.active_player.uid or (not args[0].isdigit()) 
		    		or args[0] == '0' or int(args[0]) > len(game.board.state.last_votes) ):# and uid not in ADMIN:
			bot.send_message(game.cid, "No es el momento de adivinar, no eres el que tiene que adivinar o no has ingresado algo valido para puntuar", ParseMode.MARKDOWN)
			return
		# Llego con un numero valido, mayor a zero y que esta en el rando de las respuestas		
		args_text = args[0]
		
		frase_elegida = list(game.board.state.last_votes.items())[int(args_text)-1]
		jugador_favorecido = game.playerlist[frase_elegida[0]]
		mensaje = "La frase elegida fue: *{0}* de {1}! {1} ganas 1 punto!".format(frase_elegida[1], helper.player_call(jugador_favorecido))
		jugador_favorecido.puntaje += 1
		bot.send_message(game.cid, mensaje, ParseMode.MARKDOWN)
		SayAnythingController.start_next_round(bot, game)		
			
	except Exception as e:
		bot.send_message(uid, str(e))
		log.error("Unknown error: " + str(e))

def command_continue(bot, game, uid):
	try:
		
		# Verifico en mi maquina de estados que comando deberia usar para el estado(fase) actual
		if game.board.state.fase_actual == "Proponiendo Pistas":
			# Vuelvo a mandar la pista
			SayAnythingController.call_players_to_clue(bot, game)
		elif game.board.state.fase_actual == "Revisando Pistas":
			SayAnythingController.review_clues(bot, game)
		elif game.board.state.fase_actual == "Adivinando":
			active_player = game.board.state.active_player
			bot.send_message(game.cid, "{0} estamos esperando para que hagas /guess EJEMPLO o /pass".format(helper.player_call(active_player)), ParseMode.MARKDOWN)
		elif game.board.state.fase_actual == "Finalizado":
			SayAnythingController.continue_playing(bot, game)
	except Exception as e:
		bot.send_message(game.cid, str(e))
