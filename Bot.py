import disnake
from disnake.ext import commands
from youtube_dl import YoutubeDL
import asyncio
import os

from VoteController import VoteController
from OptionsController import OptionsController
from VideoPlayer import FFMpegVideo, VideoClient
from Downloader import DownloadDispatcher
from misc import from_postfix_time
from MutableTime import HourlessTime, RelativeTime
from View import CustomModal
from TextQueueController import QueueController
from Logger import Logger
from Secrets import bot_tokens, test_guilds

import threading
import traceback
import aiohttp
import subprocess

YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist':False, 'cookiefile' : 'cookies.txt', 'cachedir' : False, 'ignoreerrors' : True}
YDL_OPTIONS_VIDEO = {'cookiefile' : 'cookies.txt'}

command_sync_flags = commands.CommandSyncFlags.default()
command_sync_flags.sync_commands_debug = True
command_sync_flags.sync_guild_commands = True

bot = commands.InteractionBot(
#	command_prefix="!",
	test_guilds = test_guilds,
	command_sync_flags = command_sync_flags
)

QueueController.bind_client(bot)

def add_looper_from_interaction(interaction, voice=None):
	loopers[interaction.author.voice.channel.id] = Looper(voice=voice, echo_message=interaction)
	return loopers[interaction.author.voice.channel.id]

queue_controllers = {}
async def queue_controller_from_interaction(interaction, auto_create=False):
	global queue_controllers
	queue_controller = queue_controllers.get(interaction.guild.id)
	channel = interaction.author.voice.channel
	if queue_controller is None and auto_create:
		# while True:
		voice = await channel.connect()
		#	await voice.disconnect()
		queue_controller = queue_controllers[interaction.guild.id] = QueueController(channel, voice, interaction)
	if not queue_controller.connected:
		try:
			voice = await interaction.author.voice.channel.connect()
		except: pass
		else:
			queue_controller.set_voice(voice)

	return queue_controller

#AUTOCOMPLETE_URLS = [r"https://www\.youtube\.com/watch*.&list=PLHCSx0BoYIoKMkia5I3qkK2FQ1ISOezMV"]
AUTOCOMPLETE_URLS = ["https://www.youtube.com/watch?list=PLHCSx0BoYIoKMkia5I3qkK2FQ1ISOezMV"]

import re
def play_autocompleter(interaction, user_input):
	return [url for url in AUTOCOMPLETE_URLS if url.startswith(user_input.lower())]

@bot.slash_command(
	dm_permission=False
)
async def play(
	interaction,
	url : str = commands.Param(default=None, autocomplete=play_autocompleter)
):
	"""
	Youtupe only supported. Play sound from a vide in voice channel.

	Parameters
	----------
	url: Youtube video url
	"""
	try:
		await interaction.response.defer()
	except: pass


	# looper = looper_from_interaction(interaction)
	# if looper is None:
	# 	voice_channel = interaction.author.voice.channel
	# 	voice = await voice_channel.connect()
	# 	looper = add_looper_from_interaction(interaction, voice)

	queue_controller = await queue_controller_from_interaction(interaction, auto_create=True)

	if url is not None:
		Logger.printline("debug", "dispatcher")
		await DownloadDispatcher.instance.download(url, queue_controller, interaction, delete=False)
	else:
		queue_controller.play()

	# if queue_controller.playing:
	# 	await interaction.edit_original_response("added to queue")

from EqualizerSource import PCMVolumeEqualizer

@bot.slash_command()
async def equa(interaction):
	"""
	Turn on equalizer. Gains from "/set_equa" command
	"""
	#test_gains = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
	queue_controller = await queue_controller_from_interaction(interaction, auto_create=False)
	if queue_controller is not None:
		queue_controller.enable_equa()
		#queue_controller._voice.source = PCMVolumeEqualizer(queue_controller._voice.source, test_gains)
	await interaction.response.defer()

@bot.slash_command()
async def set_equa(interaction, gain1 : float, gain2 : float, gain3 : float, gain4 : float, gain5 : float, gain6 : float, gain7 : float, gain8 : float, gain9 : float, gain10 : float, volume : int):
	"""
	Set "/equa" command equalizer gains and volume
	"""
	queue_controller = await queue_controller_from_interaction(interaction, auto_create=False)
	if queue_controller is not None:
		queue_controller.set_equa_options([gain1, gain2, gain3, gain4, gain5, gain6, gain7, gain8, gain9, gain10], volume)
	await interaction.response.defer()

@bot.slash_command()
async def af(interaction, audio_filter):
	"""
	Set raw ffmpeg -af options. Pass "none" to disable
	"""
	queue_controller = await queue_controller_from_interaction(interaction, auto_create=False)
	if queue_controller is not None:
		queue_controller.set_audio_filter(audio_filter)
	await interaction.response.defer()


@bot.slash_command()
async def next(interaction):
	"""
	Play next in queue
	"""
	await interaction.response.defer(with_message=True)
	queue_controller = await queue_controller_from_interaction(interaction)
	if queue_controller is None:
		await interaction.send("Not playing")
		return
	#looper.update_echo_message(interaction)
	queue_controller.next()
	await interaction.send("Playing next")

voteController = None

@bot.slash_command()
async def votegay(interaction, user : disnake.User, name : str):
	"""
	Gleb gay

	Parameters
	----------
	user: user to vote
	name: vote name
	"""
	voteController = VoteController(interaction, user.name, name)
	await voteController.send()


@bot.slash_command()
async def queue(interaction):
	"""
	Display queue
	"""
	await interaction.response.defer()
	queue_controller = await queue_controller_from_interaction(interaction)
	if queue_controller is None:
		await interaction.send("Not playing")
		return
	await queue_controller.update_interaction(interaction)
	queue_controller.echo()

loops = ["Loop off", "loop queue", "loop one item"]
@bot.slash_command()
async def loop(interaction):
	"""
	toggles loop
	"""
	queue_controller = await queue_controller_from_interaction(interaction)
	if queue_controller is None:
		await interaction.send("Not playing")
		return
	msg = loops[queue_controller.toggle_loop()]
	await interaction.send(msg)

@bot.slash_command()
async def prev(interaction):
	"""
	Play previous in queue
	"""
	queue_controller = await queue_controller_from_interaction(interaction)
	if queue_controller is None:
		await interaction.send("Not playing")
		return

	if not queue_controller.previous():
		await interaction.send("No previous")
		return
	await interaction.send("Play previous")

@bot.slash_command()
async def goto(interaction, to : str):
	"""
	Test feature
	
	Parameters
	----------
	to: time to scroll ([+|-][00s] [00m] [00h])
	"""
	queue_controller = await queue_controller_from_interaction(interaction)
	if queue_controller is None:
		await interaction.send("Not playing")
		return


	if not queue_controller.audio_time_set(from_postfix_time(to)):
		await interaction.send("failed")

@bot.slash_command()
async def jump(interaction, index : int):
	"""
	jump to item in queue

	Parameters
	----------
	index: index of item in queue
	"""
	queue_controller = await queue_controller_from_interaction(interaction)
	if queue_controller is None:
		await interaction.send("Not playing")
		return

	if not queue_controller.jump(index - 1):
		await interaction.send("jump error")
		return
	await interaction.send("jumped to %i" % index )

@bot.slash_command()
async def volume(interaction, level : int):
	"""
	sets *current* item's volume

	Parameters
	----------
	level: volume level to set as percentage (e.g 120)
	"""
	queue_controller = await queue_controller_from_interaction(interaction)
	if queue_controller is None:
		await interaction.send("Not playing")
		return

	queue_controller.set_volume(level / 100)

	await interaction.send("setted volume to {0}%".format(level))

# video_client = None

FORMAT = "bestvideo[width<=320]"
DEFAULT_FORMAT = "bestvideo"

@bot.slash_command()
async def play_video(interaction, url : str):
	"""
	чё за хуйня вообще
	"""
	await interaction.response.defer()
	global video_client
	# if video_client is None:
	# 	video_client = VideoClient(interaction, bot.loop)
	video_client = VideoClient(interaction, bot.loop)

	with YoutubeDL(YDL_OPTIONS_VIDEO) as ydl:
		selector = ydl.build_format_selector(FORMAT)
		info = ydl.extract_info(url, download=False)

		fmts = list(selector(info))
		if fmts:
			sel_fmt = fmts[0]
		else:
			sel_fmt = info["formats"][0]


	if sel_fmt is None:
		await interaction.send("err")
		return
	url = sel_fmt["url"]
	video_client.play(FFMpegVideo(source=url))

@bot.slash_command()
async def _play_raw_video(interaction, url : str):
	"""
	Полный пиздец
	"""
	await interaction.response.defer()
	global video_client
	if video_client is None:
		video_client = VideoClient(interaction, bot.loop)

	video_client.play(FFMpegVideo(source=url), skip_rate=5)

@bot.slash_command()
async def _play_raw_url(interaction, url : str):
	await interaction.response.defer()

	queue_controller = await queue_controller_from_interaction(interaction, auto_create=True)

	queue_controller.add(url, url, 0)
	queue_controller.play()

@bot.slash_command()
async def stop_video(interaction):
	"""
	Если заебало видео
	"""
	await interaction.response.defer()
	global video_client
	if video_client is not None:
		video_client.stop()

options_controller = None

@bot.slash_command()
async def options(interaction):
	"""
	Manage options
	"""
	await interaction.response.defer()
	options_controller = OptionsController()
	await options_controller.update_interaction(interaction)
	await options_controller.send_options()

@bot.slash_command(auto_sync=False)
async def setdj(interaction):
	pass
@bot.slash_command(auto_sync=False)
async def removedj(interaction):
	pass


# import signal
# def stop_all_intances(signum, frame):
# 	DownloadDispatcher.instance.stop()
# 	print("Stopped DownloadDispatcher")
# signal.signal(signal.SIGINT, stop_all_intances)

from OptionsController import RawOptionsController
from Shared import SharedOptions

def option_autocompleter(interaction, user_input):
	return RawOptionsController.instance.autocomplete_options(user_input)
def option_value_autocompleter(interaction, user_input):
	return RawOptionsController.instance.autocomplete_option_value(interaction.data.options[0].value, user_input)

option_names = commands.option_enum(list(RawOptionsController.instance.shared_options.enum_names()))

@bot.slash_command()
async def option(
	interaction,
	name: str = commands.Param(autocomplete=option_autocompleter),
	value: str = commands.Param(autocomplete=option_value_autocompleter)
):
	"""
	Set bot options
	"""
	if RawOptionsController.instance.set(name, value):
		await interaction.send("successfully setted option")
	else:
		await interaction.send("failed to set option")

async def toggle_dj_commands_a(value):
	if value is True:
		setdj_command = bot.get_slash_command("setdj")
		removedj_command = bot.get_slash_command("removedj")
		if setdj_command is not None:
			await bot.create_guild_command(831904677775278123, setdj_command.body)
		if removedj_command is not None:
			await bot.create_guild_command(831904677775278123, removedj_command.body)
		print("enabled dj commands")
	else:
		setdj_command = bot.get_guild_command_named(831904677775278123, "setdj")
		removedj_command = bot.get_guild_command_named(831904677775278123, "removedj")
		if setdj_command is not None:
			await bot.delete_guild_command(831904677775278123, setdj_command.id)
		if removedj_command is not None:
			await bot.delete_guild_command(831904677775278123, removedj_command.id)
		print("disabled dj commands")
def toggle_dj_commands(value):
	print("dj_role_enable completer")
	bot.loop.create_task(toggle_dj_commands_a(value))

SharedOptions.shared_instance().set_option_completer("dj_role_enable", toggle_dj_commands)

@disnake.ext.commands.slash_command()
async def afsaasd(interaction):
	pass

@bot.slash_command()
async def _debug_log(interaction):
	pass
@bot.slash_command(auto_sync=False)
async def _copy_queue(interaction):
	pass

@bot.slash_command()
async def save(interaction, name : str = "auto"):
	await interaction.response.defer(with_message=False)
	queue_controller = await queue_controller_from_interaction(interaction)
	if queue_controller is None:
		return
	with open(f"queues/{name}.txt", "w", encoding="utf16") as f:
		# header
		f.write("{item};{time};{filters}\n".format(
			item = queue_controller.get_current_index(),
			time = int(queue_controller.get_played_time()),
			filters = queue_controller.get_af_opts()
		))

		for url, (name, duration) in zip(queue_controller.enum_urls(), queue_controller.enum_view_items()):
			# print(url)
			name = name.replace("\n", "")
			f.write(f"{url};{name};{int(duration)}\n")
	await interaction.send("saved")

def restore_autocompleter(interaction, user_input):
	return [os.path.splitext(file)[0] for file in os.listdir("./queues") if file.startswith(user_input)]

@bot.slash_command()
async def restore(interaction, name : str = commands.Param(default="auto", autocomplete=restore_autocompleter)):
	await interaction.response.defer(with_message=False)
	queue_controller = await queue_controller_from_interaction(interaction, auto_create=True)
	if queue_controller is None:
		return

	Logger.printline("restore", name, interaction)
	try:
		with open(f"queues/{name}.txt", "r", encoding="utf16") as f:
			await interaction.edit_original_response(f"restoring")
			item, time, filters = f.readline().rstrip().split(";")

			queue_controller.clear()
			for i, line in enumerate(f):
				line = line.rstrip("\n")
				# await interaction.edit_original_response(f"restore {i}/{len(lines)}")
				if line.count(";") != 2:
					print(f"Failed to parse line {i}: {line}")
					continue
				url, name, duration = line.split(";")
				duration = int(duration)
				queue_controller.add(url, name, duration, no_refresh=True)
				# await DownloadDispatcher.instance.download(line, queue_controller, interaction, delete=False, autoplay=False)

			queue_controller.set_audio_filter(filters)
			queue_controller.jump(int(item))
			queue_controller.audio_time_set(HourlessTime(seconds=int(time)))

	except FileNotFoundError:
		print("Restore file not found")
	except Exception as e:
		print("Failed to restore.")
		print(traceback.format_exec(e))
	finally:
		queue_controller.play()
		await queue_controller.update_interaction(interaction)
		await interaction.edit_original_response("restored")

print(afsaasd)

@bot.slash_command()
async def play_file(interaction, file : disnake.Attachment):
	await interaction.response.defer()
	url = file.url
	# if os.splitext(file.name)[1] not in ["mp3", "mp4"]:
	# 	await interaction.send("only mp3, mp4 supported")
	# 	return

	queue_controller = await queue_controller_from_interaction(interaction, auto_create=True)

	Logger.printline("debug", "dispatcher")
	duration = int(float(subprocess.check_output(f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {url}").rstrip().decode("utf-8")))
	queue_controller.add(url, file.filename, duration)
	queue_controller.play(replay=False)

@bot.slash_command()
async def reconnect(interaction):
	await interaction.response.defer()

	queue_controller = await queue_controller_from_interaction(interaction, auto_create=False)
	if queue_controller is None:
		return

	queue_controller.stop()
	for voice in bot.voice_clients:
		if voice.guild.id == interaction.guild.id:
			print("disconnect")
			await voice.disconnect()
			break

	# await queue_controller.update_interaction(interaction)
	await interaction.delete_original_response()
	queue_controller.set_voice(await interaction.author.voice.channel.connect())

test_event_loop = asyncio.new_event_loop()
def test_loop_main():
	test_event_loop.run_forever()
test_loop_thread = threading.Thread(target=test_loop_main, args=())
test_loop_thread.start()

@bot.slash_command()
async def zavali_ebalo(interaction):
	queue_controller = await queue_controller_from_interaction(interaction, auto_create=False)
	if queue_controller is None:
		return

	channel = queue_controller._voice.channel
	guild = interaction.guild
	await bot.ws.voice_state(guild.id, channel.id, self_mute=True)

@bot.listen()
async def on_ready():
	await bot.change_presence(activity=disnake.Activity(type=disnake.ActivityType.listening, name="твою мамку"))
	await toggle_dj_commands_a(SharedOptions.instance.get("dj_role_enable").value)

	task = asyncio.run_coroutine_threadsafe(bot.change_presence(activity=disnake.Activity(type=disnake.ActivityType.listening, name="твою мамку")), loop=test_event_loop)
	print("task.result() => ", task.result())


bot.run(bot_tokens[3], bot=True)