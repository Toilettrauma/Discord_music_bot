import importlib

commands = []
def register_command(name):
	def decorator(function):
		global commands
		commands.append({"name":name, "function":function})
		return function
	return decorator

import Downloader
import TextQueueController
import VideoPlayer
import VoteController
import Logger
import Bot
modules = [Downloader, TextQueueController, VideoPlayer, VoteController, Logger, Bot]

@register_command("reload")
def reload():
	for module in modules:
		reloaded_module = importlib.reload(module)
		globals()[module.__name__] = reloaded_module

import sys
@register_command("exit")
def command_exit():
	sys.exit(0)

def execute_command(name):
	for command in commands:
		if command["name"] == name:
			command["function"]()
			break

while True:
	inp = input(">>> ")
	execute_command(inp)
