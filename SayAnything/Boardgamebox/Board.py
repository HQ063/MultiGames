from Constants.Cards import cartas_aventura

import random
from Boardgamebox.State import State
from Boardgamebox.Board import Board as BaseBoard

class Board(BaseBoard):
	def __init__(self, playercount, game):
		BaseBoard.__init__(self, playercount, game)
		
	def print_board(self, game):
		board = ""
		board += "--- *Estado de Partida* ---\n"
		board += "Cartas restantes: {0}\n".format(len(game.board.cartas))
		board += "Puntaje actual: {0}".format(game.board.state.progreso)

		board += "\n\n"

		board += "--- *Orden de jugadores* ---\n"
		for player in game.player_sequence:
			nombre = player.name.replace("_", " ")
			if self.state.active_player == player:
				board += "*" + nombre + "*" + " " + u"\u27A1\uFE0F" + " "
			else:
				board += nombre + " " + u"\u27A1\uFE0F" + " "
		board = board[:-3]
		board += u"\U0001F501"

		board += "\n\nEl jugador *{0}* tiene que adivinar".format(game.board.state.active_player.name)
		board += "\n\nEl jugador *{0}* revisara las pistas".format(game.board.state.reviewer_player.name)
		if len( game.board.cartas) == 0:
			board += "\n\n‼️Esta es la ultima carta del mazo‼️"
		
		return board