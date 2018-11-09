import json
import logging as log
import datetime
#import ast
import jsonpickle
import os
import psycopg2
import urllib.parse
import sys
	
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode

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

def command_resolve_exploration2(bot, update):
	# Metodo que da los datos basicos devuelve Game=None Player = None si no hay juego.
	cid, uid, game, player = get_base_data(bot, update)
	if game is not None:
		# Busco la carta y obtengo sus acciones		
		if not game.board.cartasExplorationActual:
			bot.send_message(cid, "Exploracion Actual no tiene cartas")			
		else:
			carta = cartas_aventura[game.board.cartasExplorationActual[0]]
			bot.send_message(cid, carta)
			acciones = carta["acciones"]
			index_accion_actual = 1
			accion_actual = carta["acciones"][index_accion_actual]
			bot.send_message(cid, accion_actual)
			tipo_accion_actual = accion_actual["tipo"]
			bot.send_message(cid, tipo_accion_actual)
			opciones_accion_actual = accion_actual["opciones"]			
			index_opcion_actual = 1
			opcion_actual = opciones_accion_actual[index_opcion_actual]
			bot.send_message(cid, opcion_actual)
			comandos_opcion_actual = opcion_actual["comandos"]
			index_comando_actual = 1
			comando_actual = comandos_opcion_actual[index_comando_actual]
			bot.send_message(cid, comando_actual)
						
			# Ejecuto el comando
			comando = comandos[comando_actual]
			tipo_comando = comando["tipo"]
			
			# Si el comando es automatico, lo ejecuto sin no deberia pedir argumentos
			if tipo_comando == "automatico":
				# Si el command que quiero usar tiene args se los agrego.
				if "comando_argumentos" in comando:
					getattr(sys.modules[__name__], comando["comando"])(bot, update, comando["comando_argumentos"])	
				else:
					getattr(sys.modules[__name__], comando["comando"])(bot, update)
					
			elif tipo_comando == "indicaciones":
				# Genero los botones para preguntar al usuario.
				strcid = str(game.cid)
				btns = []
				for argumento in comando["indicacion_argumentos"]:
					txtBoton = "%s" % (argumento)
					datos = strcid + "*executecommand*" + argumento + "*" + comando["comando"] + "*" + str(uid)
					#log.info("Se crea boton con datos: %s %s" % (txtBoton, datos))
					bot.send_message(cid, datos)					
					btns.append([InlineKeyboardButton(txtBoton, callback_data=datos)])     

				btnMarkup = InlineKeyboardMarkup(btns)
				#for uid in game.playerlist:
				bot.send_message(cid, comando["indicacion"], reply_markup=btnMarkup)
			else:
				# Si es final, solo gain_skill es final
				if "comando_argumentos" in comando:
					getattr(sys.modules[__name__], comando["comando"])(bot, update, comando["comando_argumentos"])	
				else:
					getattr(sys.modules[__name__], comando["comando"])(bot, update)
				
def execute_command(bot, update):
	callback = update.callback_query
	log.info('execute_command called: %s' % callback.data)
	regex = re.search("([0-9]*)\*executecommand\*([^_]*)\*(.*)\*([0-9]*)", callback.data)
	cid = int(regex.group(1))
	strcid = regex.group(1)	
	opcion = regex.group(2)
	comando = regex.group(3)
	uid = int(regex.group(4))
	
	bot.send_message(cid, "%s %s %s" % (strcid, opcion, comando, str(uid)))
	# Directamente lo ejecuto ya que tengo el argumento.
	getattr(sys.modules[__name__], comando)(bot, update, [opcion, cid, uid])
	
	

def get_img_carta(num_carta):
	carta = cartas_aventura[num_carta]
	plastilla, fila, columna = carta["plastilla"], carta["fila"], carta["columna"]	
	url_img = '/app/img/LostExpedition/plastilla%s.jpg' % (plastilla)		
	img = Image.open(url_img)
	width, height = img.size
	widthCarta, heightCarta = width/3, height/3
	# Este switch se hace para corresponder al llamado del metodo, sino tendria que haber sido columna, fila.
	columna, fila = int(fila), int(columna)
	#log.info(img.size)
	x, y = (fila*widthCarta), (columna*heightCarta)
	#log.info(x)
	#log.info(y)
	left, top, right, bottom = x, y, widthCarta+x, heightCarta+y
	cropped = img.crop( ( left, top, right, bottom ) )
	return cropped

def command_newgame_sql_command(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id
	if uid in ADMIN:
		try:
			#Check if game is in DB first
			cursor = conn.cursor()			
			log.info("Executing in DB")
			#query = "select * from games;"
			query = " ".join(args)
			cursor.execute(query)
			#dbdata = cur.fetchone()
			if cursor.rowcount > 0:
				bot.send_message(cid, 'Resultado de la consulta:')
				for table in cursor.fetchall():
					bot.send_message(cid, table)
			else:
				bot.send_message(cid, 'No se obtuvo nada de la consulta')
		except Exception as e:
			bot.send_message(cid, 'No se ejecuto el comando debido a: '+str(e))

	

# The Lost Expedition
# Generic commands for all games
def showImages(bot, cid, cartas):
	images = []
	for carta in cartas:
		images.append(get_img_carta(carta))

	widths, heights = zip(*(i.size for i in images))

	total_width = sum(widths)
	max_height = max(heights)

	new_im = Image.new('RGB', (total_width, max_height))

	x_offset = 0
	for im in images:
		new_im.paste(im, (x_offset,0))
		x_offset += im.size[0]

	bio = BytesIO()
	bio.name = 'image.jpeg'
	new_im.save(bio, 'JPEG')
	bio.seek(0)
	bot.send_photo(cid, photo=bio)
	
def save(bot, update):
	try:
		cid = update.message.chat_id
		groupName = update.message.from_user.first_name
		game = GamesController.games.get(cid, None)
		gameType = 'LostExpedition'
		save_game(cid,groupName , game, gameType )
		#bot.send_message(cid, 'Se grabo correctamente.')
		log.info('Se grabo correctamente.')
	except Exception as e:
		bot.send_message(cid, 'Error al grabar '+str(e))
		

def load(bot, update):
	cid = update.message.chat_id
	game = load_game(cid)			
	if game:
		GamesController.games[cid] = game
		bot.send_message(cid, "Juego Cargado exitosamente")				
		#bot.send_message(game.cid, game.board.print_board(game.playerlist))				
		# Remember the current player that he has to act
		#MainController.start_round(bot, game)
	else:
		bot.send_message(cid, "No existe juego")		

def get_game(cid):
	# Busco el juego actual
	game = GamesController.games.get(cid, None)	
	if game:
		# Si esta lo devuelvo.
		return game
	else:
		# Si no esta lo busco en BD y lo pongo en GamesController.games
		game = load_game(cid)
		if game:
			GamesController.games[cid] = game
			return game
		else:
			None

# Despues de cada comando que actualiza el juego se graba
def after_command(bot, update):
	save(bot, update)
	
#Lost Expedition
# Comando para hacer luego de que se achica la ruta a explorar
def after_ruta_achicada(bot, update):
	cid, uid = update.message.chat_id, update.message.from_user.id
	game = get_game(cid)
	if not game.board.cartasExplorationActual:		
		bot.send_message(cid, "Exploracion Actual no tiene cartas. Se cambia DÍA/NOCHE")
		bot.send_message(cid, "Se pierde uno de comida (Se pierde comida automaticamente, sino no hay que quitar 1 de vida de alguien y aumentar la comida)")
		command_losefood(bot, update)
		
def command_hoja_ayuda(bot, update):
	cid = update.message.chat_id
	help_text = "Eventos amarillos son obligatorios\n" + \
			"Eventos rojo son obligatorios pero tenes que elegir 1\n"  + \
			"Eventos Azules son opcionales"
	bot.send_message(cid, help_text)
	bot.send_photo(cid, photo=open('/app/img/LostExpedition/Ayuda01.jpg', 'rb'))	
	bot.send_photo(cid, photo=open('/app/img/LostExpedition/Ayuda02.jpg', 'rb'))

def command_newgame_lost_expedition(bot, update):  
	cid = update.message.chat_id
	fname = update.message.from_user.first_name
	uid = update.message.from_user.id
	try:
		game = get_game(cid)
		if game:
			bot.send_message(cid, "Hay un juego ya creado, borralo con /cancelgame.")
		else:
			# Creo el juego si no esta.
			game = Game(cid, update.message.from_user.id, "solitario")
			GamesController.games[cid] = game
			# Creo el jugador que creo el juego y lo agrego al juego
			player = Player(fname, uid)
			game.add_player(uid, player)				
			player_number = len(game.playerlist)
			bot.send_message(cid, "Se creo el juego y el usuario")
			game.board = Board(player_number, game)			
			bot.send_message(cid, "El jugador obtiene 6 cartas")
			command_drawcard(bot, update, [6])
			
			if game.tipo == 'solitario':
				#Si es un juego en solitario comienzo sacando las dos cartas del mazo y las ordeno
				command_add_exploration_deck(bot, update, [2])
				command_sort_exploration_rute(bot, update)
				bot.send_message(cid, "Ahora debes jugar dos cartas")
				
	except Exception as e:
		bot.send_message(cid, 'Error '+str(e))


		
def command_drawcard(bot, update, args):
	cid = update.message.chat_id
	uid = update.message.from_user.id
	if uid in ADMIN:
		#bot.send_message(cid, args)
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		# Si no se paso argumento paso 2 cartas.
		cantidad = int(args[0] if args else 1)		
		#log.info(game.board.cartasAventura)
		for i in range(cantidad):
			draw_card_cartasAventura(game, player.hand)		
		#log.info(game.board.cartasAventura)
		#cid = '-1001206290323'
		#log.info(player.hand)
		bot.send_message(cid, "Se han obtenido %s cartas" % cantidad)
		command_showhand(bot, update)
		after_command(bot, update)
		
def command_showhand(bot, update):	
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		bot.send_message(cid, "Mano jugador actualizada.")
		showImages(bot, cid, player.hand)
		
def command_showskills(bot, update):	
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		if not player.skills:
			bot.send_message(cid, "El jugador no tiene skills.")
		else:
			showImages(bot, cid, player.skills)

def command_increase_progreso(bot, update):	
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		game.board.progreso += 1
		if game.board.progreso == game.board.objetivoprogreso:
			bot.send_message(cid, "Ganaste")
		else:
			bot.send_message(cid, "Estas a %s de distancia, el objetivo es 9" % game.board.progreso)
		after_command(bot, update)
		'''
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		if not player.skills:
			bot.send_message(cid, "El jugador no tiene skills.")
		else:
			showImages(bot, cid, player.skills)
		'''
			
def command_losebullet(bot, update):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		player.bullets -= 1;		
		command_showstats(bot, update)
		after_command(bot, update)
		
def command_gainbullet(bot, update):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		player.bullets += 1;
		command_showstats(bot, update)
		after_command(bot, update)
		
def command_losefood(bot, update):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		player.food -= 1;
		command_showstats(bot, update)
		after_command(bot, update)
		
def command_gainfood(bot, update):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		player.food += 1;
		command_showstats(bot, update)
		after_command(bot, update)

def command_lose_life(bot, update, args):
	try:
		
		cid, uid = update.message.chat_id, update.message.from_user.id
	
	except Exception as e:
		cid, uid = args[1], args[2]
			
	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		if args[0] == "Explorador Campero":
			player.vida_explorador_campero  -=1;
		if args[0] == "Explorador Brujula":
			player.vida_explorador_brujula  -=1;
		if args[0] == "Explorador Hoja":
			player.vida_explorador_hoja  -=1;		
		command_showstats(bot, update)
		after_command(bot, update)
		
def command_gain_life(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		if args == "Explorador Campero":
			player.vida_explorador_campero  +=1;
		if args == "Explorador Brujula":
			player.vida_explorador_brujula  +=1;
		if args == "Explorador Hoja":
			player.vida_explorador_hoja  +=1;		
		command_showstats(bot, update)
		after_command(bot, update)
		
def command_vida_explorador_campero(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		player.vida_explorador_campero  -= int(args[0] if args else 1);
		command_showstats(bot, update)
		after_command(bot, update)
		
def command_vida_explorador_brujula(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		player.vida_explorador_brujula  -= int(args[0] if args else 1);
		command_showstats(bot, update)
		after_command(bot, update)
		
def command_vida_explorador_hoja(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		player.vida_explorador_hoja  -= int(args[0] if args else 1);
		command_showstats(bot, update)
		after_command(bot, update)

def command_add_exploration(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		# Primera carta de la mano si no pone argumentos
		carta = int(args[0] if args else 1)-1
		game.board.cartasExplorationActual.append(player.hand.pop(carta))
		bot.send_message(cid, "Se ha agregado la carta al final de la ruta")
		after_command(bot, update)
		#command_showhand(bot, update)
		#command_show_exploration(bot, update)		

def command_add_exploration_first(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		# Primera carta de la mano si no pone argumentos
		carta = int(args[0] if args else 1)-1
		game.board.cartasExplorationActual.insert(0, player.hand.pop(carta))
		bot.send_message(cid, "Se ha agregado la carta al principio de la ruta")
		after_command(bot, update)
		#command_showhand(bot, update)
		#command_show_exploration(bot, update)		
		

def draw_card_cartasAventura(game, destino):
	destino.append(game.board.cartasAventura.pop(0))
	# Me fijo si hay carta en cartasAventura si no hay más mezclo el descarte en el mazo de aventura
	if not game.board.cartasAventura:
		game.board.cartasAventura = random.sample(game.board.discards, len(game.board.discards))
		game.board.discards = []
		game.board.amount_shuffled += 1
		if game.board.amount_shuffled == 1:
			bot.send_message(cid, "Se ha mezclado el mazo y se debe consumir 1 de comida")
			#for uid in game.playerlist:
			#	player = game.playerlist[uid]
		else:
			bot.send_message(cid, "Se ha perdido la partida porque se ha mezclado el mazo dos veces. /cancelgame")
			
		
		
def command_add_exploration_deck(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return		
		#cid = '-1001206290323'
		cantidad = int(args[0] if args else 1)		
		log.info(game.board.cartasAventura)
		for i in range(cantidad):			
			draw_card_cartasAventura(game, game.board.cartasExplorationActual)
		bot.send_message(cid, "Se ha agregado %s cartas al final de la ruta desde el mazo" % cantidad)
		after_command(bot, update)
		#log.info(game.board.cartasAventura)
		#command_show_exploration(bot, update)
		
def command_add_exploration_deck_first(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return		
		#cid = '-1001206290323'
		cantidad = int(args[0] if args else 1)-1		
		
		game.board.cartasExplorationActual.insert(0, game.board.cartasExplorationActual.pop(cantidad))
		bot.send_message(cid, "Se ha agregado la carta %s al principio de la ruta" % cantidad+1)
		after_command(bot, update)
		#log.info(game.board.cartasAventura)
		#command_show_exploration(bot, update)		
		
def command_show_exploration(bot, update):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return		
		#cid = '-1001206290323'		
		if not game.board.cartasExplorationActual:
			bot.send_message(cid, "Exploracion Actual no tiene cartas")
		else:
			bot.send_message(cid, "Exploracion Actual")
			showImages(bot, cid, game.board.cartasExplorationActual)

def command_sort_exploration_rute(bot, update):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		game.board.cartasExplorationActual.sort()
		command_show_exploration(bot, update)
		after_command(bot, update)

def command_swap_exploration(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return		
		#cid = '-1001206290323'
		# Me fijo que haya pasado los dos arguemtnso
		if len(args) < 2:
			bot.send_message(cid, "Se tienen que ingresar 2 argumentos")
			return			
		a, b =  int(args[0])-1, int(args[1])-1		
		game.board.cartasExplorationActual[b], game.board.cartasExplorationActual[a] = game.board.cartasExplorationActual[a], game.board.cartasExplorationActual[b]		
		bot.send_message(cid, "Se han intercambiado las cartas %s y %s de la ruta" % (a, b))
		after_command(bot, update)
		#command_show_exploration(bot, update)

# Remove se usara para resolver y para remover cartas por accion de otras cartas		
def command_remove_exploration(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		# Defecto saco la de la izquierda
		item_to_remove = int(args[0] if args else 2)-1	
		try:			
			game.board.discards.append(game.board.cartasExplorationActual.pop(item_to_remove))
			bot.send_message(cid, "La carta se ha eliminado de la ruta")
			after_ruta_achicada(bot, update)
			after_command(bot, update)
			#command_show_exploration(bot, update)
		except Exception as e:
			bot.send_message(cid, "El remover carta de exploracion ha fallado debido a: "+str(e))
			

def command_remove_last_exploration(bot, update):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		command_remove_exploration(bot, update, [len(game.board.cartasExplorationActual)])		
		
		
# Resolver es basicamente remover pero la de mas a la izquierda.
def command_resolve_exploration(bot, update):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		command_remove_exploration(bot, update, [1])

		
def command_gain_skill(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		# Defecto saco la de la izquierda
		item_to_remove = int(args[0] if args else 1)-1		
		player.skills.append(game.board.cartasExplorationActual.pop(item_to_remove))
		bot.send_message(cid, "La carta de la ruta ha sido obtenida como skill")
		after_ruta_achicada(bot, update)
		after_command(bot, update)
		#command_show_exploration(bot, update)
		
def command_use_skill(bot, update, args):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]
		#cid = '-1001206290323'
		# Defecto saco la de la izquierda
		item_to_remove = int(args[0] if args else 1)-1		
		game.board.discards.append(player.skills.pop(item_to_remove))
		bot.send_message(cid, "La carta de la skill ha sido utilizada y puesta en el descarte.")
		after_command(bot, update)
		#command_show_exploration(bot, update)
		
def command_sort_hand(bot, update):
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]	
		player.hand.sort()		
		command_showhand(bot, update)
		after_command(bot, update)
		
def command_showstats(bot, update):
	log.info('command_showstats called')
	cid, uid = update.message.chat_id, update.message.from_user.id	
	if uid in ADMIN:
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		player = game.playerlist[uid]		
		bot.send_message(cid, player.print_stats())

def command_help(bot, update):
	cid = update.message.chat_id
	'''
	help_text = "Eventos amarillos son obligatorios\n" + \
	"Eventos rojo son obligatorios pero tenes que elegir 1\n"  + \
	"Eventos Azules son opcionales\n"
	'''
	help_text = "\nLos siguientes comandos estan disponibles:\n"
	for i in commands:
		help_text += i + "\n"
	bot.send_message(cid, help_text)
		
def command_symbols(bot, update):
	cid = update.message.chat_id
	url_img = '/app/img/LostExpedition/Ayuda01.jpg'	
	img = Image.open(url_img)
	bot.send_photo(cid, photo=bio)
	url_img = '/app/img/LostExpedition/Ayuda02.jpg'	
	img = Image.open(url_img)
	bot.send_photo(cid, photo=bio)

def command_reglas(bot, update):
	cid = update.message.chat_id
	texto_reglas = "Solitario: \n" + \
			"*Dia*: Obten 6 cartas. 2 mazo, 2 mano, 1 mazo, 1 mano.\n*Se ordenan por número.*\nResuelve.\n*Pierde 1 comida.*\n" + \
			"*Noche*: Primera de la mano. Poner de mazo o mano hasta completar 6.\n*Se puede poner adelante o atras en la ruta.*\nResuelve.\n*Pierde 1 comida.* Ir a día."			
	
	bot.send_message(cid, texto_reglas, ParseMode.MARKDOWN)

def command_lose_camp(bot, update, args):
	cid, uid, game, player = get_base_data(bot, update)
	if game is None:
		return
	if args == "Explorador Campero":
		player.vida_explorador_campero  -=1;
	if args == "Explorador Brujula":
		player.vida_explorador_brujula  -=2;
	if args == "Explorador Hoja":
		player.vida_explorador_hoja  -=2;
	
def command_lose_compass(bot, update, args):
	cid, uid, game, player = get_base_data(bot, update)
	if game is None:
		return
	if args == "Explorador Campero":
		player.vida_explorador_campero  -=2;
	if args == "Explorador Brujula":
		player.vida_explorador_brujula  -=1;
	if args == "Explorador Hoja":
		player.vida_explorador_hoja  -=2;
	
def command_lose_leaf(bot, update, args):
	cid, uid, game, player = get_base_data(bot, update)
	if game is None:
		return
	if args == "Explorador Campero":
		player.vida_explorador_campero  -=2;
	if args == "Explorador Brujula":
		player.vida_explorador_brujula  -=2;
	if args == "Explorador Hoja":
		player.vida_explorador_hoja  -=1;
	
def command_lose_explorer(bot, update, args):
	cid, uid, game, player = get_base_data(bot, update)
	if game is None:
		return
	if args == "Explorador Campero":
		player.vida_explorador_campero  = 0;
	if args == "Explorador Brujula":
		player.vida_explorador_brujula  = 0;
	if args == "Explorador Hoja":
		player.vida_explorador_hoja  = 0;
		
def get_base_data(bot, update):	
	cid, uid = update.message.chat_id, update.message.from_user.id
	if uid in ADMIN:		
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return cid, uid, None, None
		player = game.playerlist[uid]
		return cid, uid, game, player
	else:
		return cid, uid, None, None		
		
def command_prueba(bot, update, args):
	#log.info(update.message.from_user.id)
	#log.info(update.message.chat_id)
	uid = update.message.from_user.id
	if uid in ADMIN:
		cid = '-1001206290323'
		#update.message.chat_id
		game = get_game(cid)
		if not game:
			bot.send_message(cid, "No hay juego creado en este chat")
			return
		cartas_juego_actual =  random.sample([*cartas_aventura], len([*cartas_aventura]))		
		cartas_mañana = []		
		for i in range(6):
			cartas_mañana.append(cartas_juego_actual.pop(0))				
		cartas_mañana.sort()
		showImages(bot, cid, cartas_mañana)		

commands = [  # command description used in the "help" command
	'/help - Muestra ayuda sobre los comandos',
	'/newgamelostexpedition - Nuevo Juego de Lost Expedition',
	'/drawcard  - Obtiene X cartas, defecto 2',
	'/losebullet  - Resta 1 bala',
	'/gainbullet - Gana 1 bala',
	'/losefood - Pierde 1 comida',
	'/gainfood  - Gana 1 de comida',
	'/stats  - Status actual',
	'/campero - Quita/agrega vida explorador, defecto quita 1 vida. Ej: /campero -1 agrega 1 vida',
	'/brujula - Quita/agrega vida explorador, defecto quita 1 vida. Ej: /brujula -1 agrega 1 vida',
	'/hoja - Quita/agrega vida explorador, defecto quita 1 vida. Ej: /hoja -1 agrega 1 vida',
	'/addexplorationfromhand - Agrega carta a exploracion de la mano por defecto la primera',
	'/addexplorationfromdeck - Agrega carta a exploracion del mazo',
	'/swapexploration X Y- Intercambia dos cartas de exploracion Ej: /swapexploratio 2 4',
	'/removeexploration - remueve una carta de exploracion por defecto la primera. Ej: /removeexploration 2',
	'/showexploration - Muestra la exploracion actual',
	'/showhand - Muestra la mano actual',
	'/sortexploration - Ordena la exploracion actual de menor a mayor',
	'/sorthand - Ordena la mano del jugador de menor a mayor',
	'/save - Graba el juego',
	'/load - Obtiene el juego guardado',
	'/delete - Borra el juego actual'	
]

symbols = [
    u"\u25FB\uFE0F" + ' Empty field without special power',
    u"\u2716\uFE0F" + ' Field covered with a card',  # X
    u"\U0001F52E" + ' Presidential Power: Policy Peek',  # crystal
    u"\U0001F50E" + ' Presidential Power: Investigate Loyalty',  # inspection glass
    u"\U0001F5E1" + ' Presidential Power: Execution',  # knife
    u"\U0001F454" + ' Presidential Power: Call Special Election',  # tie
    u"\U0001F54A" + ' Liberals win',  # dove
    u"\u2620" + ' Fascists win'  # skull
]


		
		

	


def command_board(bot, update):
	cid = update.message.chat_id
	if cid in GamesController.games.keys():
		game = GamesController.games[cid]
		if game.board:			
			bot.send_message(cid, game.board.print_board(game.playerlist))
		else:
			bot.send_message(cid, "There is no running game in this chat. Please start the game with /startgame")
	else:
		bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")

def command_start(bot, update):
    cid = update.message.chat_id
    bot.send_message(cid,"Lost expedition.")
    command_help(bot, update)


def command_rules(bot, update):
    cid = update.message.chat_id
    btn = [[InlineKeyboardButton("Rules", url="http://www.secrethitler.com/assets/Secret_Hitler_Rules.pdf")]]
    rulesMarkup = InlineKeyboardMarkup(btn)
    bot.send_message(cid, "Read the official Secret Hitler rules:", reply_markup=rulesMarkup)


# pings the bot
def command_ping(bot, update):
    cid = update.message.chat_id
    bot.send_message(cid, 'pong - v0.3')


# prints statistics, only ADMIN
def command_stats(bot, update):
	cid = update.message.chat_id
	if cid == ADMIN:		
		bot.send_message(cid, "Estadisticas pronto...")

def command_join(bot, update, args):
	# I use args for testing. // Remove after?
	groupName = update.message.chat.title
	cid = update.message.chat_id
	groupType = update.message.chat.type
	game = GamesController.games.get(cid, None)
	if len(args) <= 0:
		# if not args, use normal behaviour
		fname = update.message.from_user.first_name
		uid = update.message.from_user.id
	else:
		uid = update.message.from_user.id
		if uid == ADMIN:
			for i,k in zip(args[0::2], args[1::2]):
				fname = i
				uid = int(k)
				player = Player(fname, uid)
				game.add_player(uid, player)
				log.info("%s (%d) joined a game in %d" % (fname, uid, game.cid))
	
	if groupType not in ['group', 'supergroup']:
		bot.send_message(cid, "You have to add me to a group first and type /newgame there!")
	elif not game:
		bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
	elif game.board:
		bot.send_message(cid, "The game has started. Please wait for the next game!")
	elif uid in game.playerlist:
		bot.send_message(game.cid, "You already joined the game, %s!" % fname)
	elif len(game.playerlist) >= 9:
		bot.send_message(game.cid, "You have reached the maximum amount of players. Please start the game with /startgame!")
	else:
		#uid = update.message.from_user.id
		player = Player(fname, uid)
		try:
			#Commented to dont disturb player during testing uncomment in production
			bot.send_message(uid, "You joined a game in %s. I will soon tell you your secret role." % groupName)			 
			game.add_player(uid, player)
			log.info("%s (%d) joined a game in %d" % (fname, uid, game.cid))
			if len(game.playerlist) > 4:
				bot.send_message(game.cid, fname + " has joined the game. Type /startgame if this was the last player and you want to start with %d players!" % len(game.playerlist))
			elif len(game.playerlist) == 1:
				bot.send_message(game.cid, "%s has joined the game. There is currently %d player in the game and you need 5-10 players." % (fname, len(game.playerlist)))
			else:
				bot.send_message(game.cid, "%s has joined the game. There are currently %d players in the game and you need 5-10 players." % (fname, len(game.playerlist)))
		except Exception:
			bot.send_message(game.cid,
				fname + ", I can\'t send you a private message. Please go to @xapi_prototype_bot and click \"Start\".\nYou then need to send /join again.")


def command_startgame(bot, update):
	log.info('command_startgame called')
	groupName = update.message.chat.title
	cid = update.message.chat_id
	game = GamesController.games.get(cid, None)
	if not game:
		bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
	elif game.board:
		bot.send_message(cid, "The game is already running!")
	elif update.message.from_user.id != game.initiator and bot.getChatMember(cid, update.message.from_user.id).status not in ("administrator", "creator"):
		bot.send_message(game.cid, "Only the initiator of the game or a group admin can start the game with /startgame")
	elif len(game.playerlist) < 5:
		bot.send_message(game.cid, "There are not enough players (min. 5, max. 10). Join the game with /join")
	else:
		player_number = len(game.playerlist)
		MainController.init_game(bot, game, game.cid, player_number)		
		game.board = Board(player_number, game)
		log.info(game.board)
		log.info("len(games) Command_startgame: " + str(len(GamesController.games)))
		game.shuffle_player_sequence()
		game.board.state.player_counter = 0
		bot.send_message(game.cid, game.board.print_board(game.playerlist))
		#group_name = update.message.chat.title
		#bot.send_message(ADMIN, "Game of Secret Hitler started in group %s (%d)" % (group_name, cid))		
		#MainController.start_round(bot, game)
		#save_game(cid, groupName, game)

def command_cancelgame(bot, update):
	log.info('command_cancelgame called')
	cid = update.message.chat_id	
	#Always try to delete in DB
	try:
		delete_game(cid)
		if cid in GamesController.games.keys():
			del GamesController.games[cid]
		bot.send_message(cid, "Borrado exitoso.")
	except Exception as e:
		bot.send_message(cid, "El borrado ha fallado debido a: "+str(e))	

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
							history_text += "%s registered a vote.\n" % (game.playerlist[player.uid].name)
						else:
							history_text += "%s didn't register a vote.\n" % (game.playerlist[player.uid].name)
					bot.send_message(cid, history_text)
				else:
					bot.send_message(cid, "Five minutes must pass to see the votes") 
		else:
			bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
	except Exception as e:
		bot.send_message(cid, str(e))

def command_calltovote(bot, update):
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
					# Only remember to vote to players that are still in the game
					history_text = ""
					for player in game.player_sequence:
						# If the player is not in last_votes send him reminder
						if player.uid not in game.board.state.last_votes:
							history_text += "It's time to vote [%s](tg://user?id=%d).\n" % (game.playerlist[player.uid].name, player.uid)
					bot.send_message(cid, text=history_text, parse_mode=ParseMode.MARKDOWN)
				else:
					bot.send_message(cid, "Five minutes must pass to see call to vote") 
		else:
			bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
	except Exception as e:
		bot.send_message(cid, str(e))
        
def command_showhistory(bot, update):
	#game.pedrote = 3
	try:
		#Send message of executing command   
		cid = update.message.chat_id
		#Check if there is a current game 
		if cid in GamesController.games.keys():
			game = GamesController.games.get(cid, None)  
			#bot.send_message(cid, "Current round: " + str(game.board.state.currentround + 1))
			uid = update.message.from_user.id
			history_text = "History:\n\n" 
			for x in game.history:
				history_text += x + "\n\n"

			bot.send_message(uid, history_text, ParseMode.MARKDOWN)
			#bot.send_message(cid, "I sent you the history to our private chat")			
		else:
			bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
	except Exception as e:
		bot.send_message(cid, str(e))
		log.error("Unknown error: " + str(e))  
		
def command_claim(bot, update, args):
	#game.pedrote = 3
	try:
		#Send message of executing command   
		cid = update.message.chat_id
		#Check if there is a current game 
		if cid in GamesController.games.keys():
			uid = update.message.from_user.id
			game = GamesController.games.get(cid, None)			
			if uid in game.playerlist:				
				if game.board.state.currentround != 0:
					if len(args) > 0:
						#Data is being claimed
						claimtext = ' '.join(args)
						claimtexttohistory = "Player %s claims: %s" % (game.playerlist[uid].name, claimtext)
						bot.send_message(cid, "Your claim: %s was added to the history." % (claimtext))
						game.history[game.board.state.currentround - 1] += "\n\n%s" % (claimtexttohistory)
					else:					
						bot.send_message(cid, "You have to send a message to claim.")

				else:
					bot.send_message(cid, "You can't claim in the first round")
			else:
				bot.send_message(cid, "You must be a player to claim something in the game.")
				
		else:
			bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
	except Exception as e:
		bot.send_message(cid, str(e))
		log.error("Unknown error: " + str(e))    
		
def save_game(cid, groupName, game, gameType):
	try:
		#Check if game is in DB first
		cur = conn.cursor()			
		log.info("Searching Game in DB")
		query = "select * from games where id = %s;"
		cur.execute(query, [cid])
		dbdata = cur.fetchone()
		if cur.rowcount > 0:
			log.info('Updating Game')
			gamejson = jsonpickle.encode(game)
			log.info(gamejson)
			#query = "UPDATE games SET groupName = %s, data = %s WHERE id = %s RETURNING data;"
			query = "UPDATE games SET groupName = %s, tipojuego = %s, data = %s WHERE id = %s;"
			cur.execute(query, (groupName, gameType, gamejson, cid))
			#log.info(cur.fetchone()[0])
			conn.commit()		
		else:
			log.info('Saving Game in DB')
			gamejson = jsonpickle.encode(game)
			log.info(gamejson)
			query = "INSERT INTO games(id, groupName, tipojuego, data) VALUES (%s, %s, %s, %s) RETURNING data;"
			#query = "INSERT INTO games(id , groupName  , data) VALUES (%s, %s, %s) RETURNING data;"
			cur.execute(query, (cid, groupName, gameType, gamejson))
			#log.info(cur.fetchone()[0])
			conn.commit()
	except Exception as e:
		bot.send_message(cid, 'No se grabo debido al siguiente error: '+str(e))

def load_game(cid):
	cur = conn.cursor()			
	log.info("Searching Game in DB")
	query = "SELECT * FROM games WHERE id = %s;"
	cur.execute(query, [cid])
	dbdata = cur.fetchone()

	if cur.rowcount > 0:
		log.info("Game Found")
		jsdata = dbdata[3]
		
		log.info(dbdata[0])
		log.info(dbdata[1])
		log.info(dbdata[2])
		log.info(dbdata[3])
		#log.info("jsdata = %s" % (jsdata))				
		game = jsonpickle.decode(jsdata)
		
		# For some reason the decoding fails when bringing the dict playerlist and it changes it id from int to string.
		# So I have to change it back the ID to int.				
		temp_player_list = {}		
		for uid in game.playerlist:
			temp_player_list[int(uid)] = game.playerlist[uid]
		game.playerlist = temp_player_list		
		#bot.send_message(cid, game.print_roles())
		return game
	else:
		log.info("Game Not Found")
		return None

def delete_game(cid):
	cur = conn.cursor()
	log.info("Deleting Game in DB")
	query = "DELETE FROM games WHERE id = %s;"
	cur.execute(query, [cid])
	conn.commit()
	
def command_ver(bot, update, args):
	try:
		#Send message of executing command   
		cid = update.message.chat_id
		#bot.send_message(cid, "Looking for history...")
		#Check if there is a current game 
		if cid in GamesController.games.keys():
			game = GamesController.games.get(cid, None)
			uid = update.message.from_user.id
			if len(args) > 0:
				player = game.find_player(args[0])
				if player:
					bot.send_message(uid, "El jugador %s %s esta poseido" % (player.name, "" if player.poseido else "no")) 
				else:
					bot.send_message(cid, "El jugador no existe en esta partida") 
			else:					
				bot.send_message(cid, "Se tiene que pasar un jugador para ver.") 
		else:
			bot.send_message(cid, "No hay juego en este chat. Crea un juego con /newgame")
	except Exception as e:
		bot.send_message(cid, str(e))
		
def command_otra(bot, update, args):
	try:
		#Send message of executing command   
		cid = update.message.chat_id
		#bot.send_message(cid, "Looking for history...")
		#Check if there is a current game 
		if cid in GamesController.games.keys():
			game = GamesController.games.get(cid, None)
			uid = update.message.from_user.id
			if len(args) > 0:
				player = game.find_player(args[0])
				if player:
					bot.send_message(uid, "El jugador '%s ha sido afectado por acción 'otra" % (player.name)) 
				else:
					bot.send_message(cid, "El jugador no existe en esta partida") 
			else:					
				bot.send_message(cid, "Se tiene que pasar un jugador para ver.") 
		else:
			bot.send_message(cid, "No hay juego en este chat. Crea un juego con /newgame")
	except Exception as e:
		bot.send_message(cid, str(e))

def command_limpiar(bot, update, args):
	try:
		#Send message of executing command   
		cid = update.message.chat_id
		#bot.send_message(cid, "Looking for history...")
		#Check if there is a current game 
		if cid in GamesController.games.keys():
			game = GamesController.games.get(cid, None)
			
			if len(args) > 0:
				player = game.find_player(args[0])
				if player:
					if len(args) > 1:
						try:							
							player.tokens_posesion -= int(args[1])
							bot.send_message(cid, "El jugador %s ha perdido %s %s de posesión" % (args[0], args[1], "tokens" if int(args[1]) > 1 else "token"))								
							bot.send_message(game.cid, game.board.print_board(game.playerlist))
						except Exception as e:
							bot.send_message(cid, str(e))
					else:
						player.tokens_posesion -= 1
						bot.send_message(cid, "El jugador %s ha perdido un token de posesión" % (args[0]))
						bot.send_message(game.cid, game.board.print_board(game.playerlist))
				else:
					bot.send_message(cid, "El jugador no existe en esta partida") 
			else:				
				'''
				for player in game.player_sequence:
					player.tokens_posesion -= 1							
				bot.send_message(cid, "Todos los jugadores han ganado un token de posesión") 
				bot.send_message(game.cid, game.board.print_board(game.playerlist))
				'''
				bot.send_message(cid, "Se debe elegir a un jugador") 
		else:
			bot.send_message(cid, "No hay juego en este chat. Crea un juego con /newgame")
	except Exception as e:
		bot.send_message(cid, str(e))
		
def command_infect(bot, update, args):
	try:
		#Send message of executing command   
		cid = update.message.chat_id
		#bot.send_message(cid, "Looking for history...")
		#Check if there is a current game 
		if cid in GamesController.games.keys():
			game = GamesController.games.get(cid, None)
			
			if len(args) > 0:
				player = game.find_player(args[0])
				if player:
					if len(args) > 1:
						try:							
							player.tokens_posesion += int(args[1])
							bot.send_message(cid, "El jugador %s ha ganado %s %s de posesión" % (args[0], args[1], "tokens" if int(args[1]) > 1 else "token"))								
							bot.send_message(game.cid, game.board.print_board(game.playerlist))
						except Exception as e:
							bot.send_message(cid, str(e))
					else:
						player.tokens_posesion += 1
						bot.send_message(cid, "El jugador %s ha ganado un token de posesión" % (args[0]))
						bot.send_message(game.cid, game.board.print_board(game.playerlist))
				else:
					bot.send_message(cid, "El jugador no existe en esta partida") 
			else:				
				for player in game.player_sequence:
					player.tokens_posesion += 1							
				bot.send_message(cid, "Todos los jugadores han ganado un token de posesión") 
				bot.send_message(game.cid, game.board.print_board(game.playerlist))
		else:
			bot.send_message(cid, "No hay juego en este chat. Crea un juego con /newgame")
	except Exception as e:
		bot.send_message(cid, str(e))
		
def call_to_action(bot, update):
	try:
		#Send message of executing command   
		cid = update.message.chat_id
		#bot.send_message(cid, "Looking for history...")
		#Check if there is a current game 
		if cid in GamesController.games.keys():
			game = GamesController.games.get(cid, None)
			MainController.start_round(bot, game)		
		else:
			bot.send_message(cid, "No hay juego en este chat. Crea un juego con /newgame")
	except Exception as e:
		bot.send_message(cid, str(e))
		
#Testing commands
def command_ja(bot, update):
	uid = update.message.from_user.id
	if uid == ADMIN:
		cid = update.message.chat_id
		game = GamesController.games.get(cid, None)
		answer = "Ja"
		for uid in game.playerlist:
			game.board.state.last_votes[uid] = answer
		MainController.count_votes(bot, game)
	

def command_nein(bot, update):	
	uid = update.message.from_user.id
	if uid == ADMIN:
		cid = update.message.chat_id
		game = GamesController.games.get(cid, None)
		answer = "Nein"
		for uid in game.playerlist:
			game.board.state.last_votes[uid] = answer
		MainController.count_votes(bot, game)

def command_elegimos(bot, update, args):
	uid = update.message.from_user.id
	if uid == ADMIN:
		if len(args) > 0:
			cid = update.message.chat_id
			game = GamesController.games.get(cid, None)		
			for uid in game.playerlist:
				game.board.state.last_votes[uid] = args[0]
			MainController.count_actions(bot, game)
		

# Secret Moon

secret_moon_cid = '-1001206290323'

def command_newgame_secret_moon(bot, update, args):  
	cid = update.message.chat_id
	
	try:
		game = GamesController.games.get(secret_moon_cid, None)		
		if game:
			bot.send_message(cid, "There is currently a game running.")
		else:			
			#Search game in DB
			game = load_game(cid)			
			if game:
				GamesController.games[cid] = game
				bot.send_message(cid, "There is currently a game running. If you want to end it please type /cancelgame!")				
				bot.send_message(game.cid, game.board.print_board(game.playerlist))				
				# Remember the current player that he has to act
				MainController.start_round(bot, game)
			else:
				GamesController.games[cid] = Game(secret_moon_cid, update.message.from_user.id)
				bot.send_message(secret_moon_cid, "New game created! Each player has to /joinsecretmoon in my private chat.\nThe initiator of this game (or the admin) can /join too and type /startgamesecretmoon when everyone has joined the game!")
						
	except Exception as e:
		bot.send_message(cid, str(e))
		
def command_join_secret_moon(bot, update):
	# I use args for testing. // Remove after?
	groupName = update.message.chat.title
	cid = update.message.chat_id
	groupType = update.message.chat.type
	game = GamesController.games.get(cid, None)
	
	if not game:
		bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
	elif game.board:
		bot.send_message(cid, "The game has started. Please wait for the next game!")
	elif uid in game.playerlist:
		bot.send_message(game.cid, "You already joined the game, %s!" % fname)
	elif len(game.playerlist) >= 7:
		bot.send_message(game.cid, "You have reached the maximum amount of players. Please start the game with /startgame!")
	else:
		#uid = update.message.from_user.id
		player = Player(fname, uid)
		try:
			#Commented to dont disturb player during testing uncomment in production
			bot.send_message(uid, "You joined a game in %s. I will soon tell you your secret role." % groupName)			 
			game.add_player(uid, player)
			log.info("%s (%d) joined a game in %d" % (fname, uid, game.cid))
			if len(game.playerlist) > 4:
				bot.send_message(game.cid, fname + " has joined the game. Type /startgame if this was the last player and you want to start with %d players!" % len(game.playerlist))
			elif len(game.playerlist) == 1:
				bot.send_message(game.cid, "%s has joined the game. There is currently %d player in the game and you need 5-8 players." % (fname, len(game.playerlist)))
			else:
				bot.send_message(game.cid, "%s has joined the game. There are currently %d players in the game and you need 5-8 players." % (fname, len(game.playerlist)))
		except Exception:
			bot.send_message(game.cid,
				fname + ", I can\'t send you a private message. Please go to @xapi_prototype_bot and click \"Start\".\nYou then need to send /join again.")

			
def command_startgame_secret_moon(bot, update):
	log.info('command_startgame called')
	groupName = update.message.chat.title
	cid = update.message.chat_id
	game = GamesController.games.get(secret_moon_cid, None)
	if not game:
		bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
	elif game.board:
		bot.send_message(cid, "The game is already running!")
	elif uid != ADMIN:
		bot.send_message(game.cid, "Only the Master Administrator can start the game")
	elif len(game.playerlist) < 4:
		bot.send_message(game.cid, "There are not enough players (min. 5, max. 8). Join the game with /join")
	else:
		player_number = len(game.playerlist)
		MainController.init_game(bot, game, game.cid, player_number)		
		game.board = Board(player_number, game)
		log.info(game.board)
		log.info("len(games) Command_startgame: " + str(len(GamesController.games)))
		game.shuffle_player_sequence()
		game.board.state.player_counter = 0
		bot.send_message(game.cid, game.board.print_board(game.playerlist))
		#group_name = update.message.chat.title
		#bot.send_message(ADMIN, "Game of Secret Hitler started in group %s (%d)" % (group_name, cid))		
		#MainController.start_round(bot, game)
		#save_game(cid, groupName, game)

# End Secret Moon
