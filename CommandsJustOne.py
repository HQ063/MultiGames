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

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode

import Commands
import MainController
import GamesController
from Constants.Config import STATS
from Boardgamebox.Board import Board
from Boardgamebox.Game import Game
from Boardgamebox.Player import Player
from Boardgamebox.State import State
from Constants.Config import ADMIN
from collections import namedtuple

from PIL import Image
from io import BytesIO

# Objetos que uso de prueba estaran en el state
from Constants.Cards import cartas_aventura
from Constants.Cards import opciones_opcional
from Constants.Cards import opciones_choose_posible_role
from Constants.Cards import modos_juego

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

def command_newgame_justone(bot, update):
	cid = update.message.chat_id
	fname = update.message.from_user.first_name
	uid = update.message.from_user.id
	groupName = update.message.chat.title
	try:
		game = get_game(cid)
		if game:
		
			bot.send_message(cid, "Hay un juego ya creado, borralo con /delete.")
		else:
			# Creo el juego si no esta.
			game = Game(cid, update.message.from_user.id, "JustOne" ,"cooperativo", groupName)
			GamesController.games[cid] = game
			# Creo el jugador que creo el juego y lo agrego al juego
			player = Player(fname, uid)
			game.add_player(uid, player)
			player_number = len(game.playerlist)
			bot.send_message(cid, "Se creo el juego y se ingreso como jugador al creador")
			game.board = Board(player_number, game)
			bot.send_message(cid, "Vamos a llegar al dorado. Es un hermoso /dia!")
			
			'''
			if game.tipo == 'solitario':
				command_drawcard(bot, update, [6])
				#Si es un juego en solitario comienzo sacando las dos cartas del mazo y las ordeno
				#bot.send_message(cid, "Se agregan dos cartas a la epxloracion")
				command_add_exploration_deck(bot, update, [2])
				#bot.send_message(cid, "Se ordena el mazo de exploración")
				command_sort_exploration_rute(bot, update)
				bot.send_message(cid, "Ahora debes jugar dos cartas")
			'''
				
	except Exception as e:
		bot.send_message(cid, 'Error '+str(e))
