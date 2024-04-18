import disnake
import threading
import asyncio
from datetime import datetime, time as datetime_time
from typing import NamedTuple, Union

from misc import classproperty, iso_to_seconds, seconds_to_iso, time_to_iso
from Shared import SharedOptions
from MutableTime import HourlessTime, RelativeTime
from Downloader import DownloadDispatcher, DownloaderError
from Logger import Logger
from View import CustomModal

from time import perf_counter

import random
import math

ESC = chr(0x1b) + "["
ESC_RED = ESC + "31m"
ESC_RES = ESC + "0m"
ESC_GREEN = ESC + "32m"
ESC_YEL = ESC + "33m"
ESC_ORANGE = ESC + "38:5:214"

def color_str(string, color):
	return f"{color}{string}{ESC_RES}"

class Item:
	def __init__(self, q_controller, index, name, duration):
		self._q_controller = q_controller
		self._index = index
		self.name = name
		self.duration = duration
		self.duration_time = HourlessTime(seconds=duration)
		self._description = None
		self._selected = False
		self._paused = False
		self._errored = False
	def _get_total_time(self):
		return HourlessTime(seconds=self._q_controller.get_played_time()).strftime(
			f"{ESC_YEL}%H{ESC_RES}:{ESC_YEL}%M{ESC_RES}:{ESC_YEL}%S{ESC_RES}"
		)
	def _format(self):
		if self._selected:
			name = color_str(self.name, ESC_RED)
		elif self._errored:
			name = color_str(self.name, ESC_YEL)
		else:
			name = self.name
		self._description = "{index}) {name} {duration}".format(
			index = f"{color_str(self._index + 1, ESC_GREEN)}",
			name = name,
			duration = (f"({self._get_total_time()}-" if self._selected else "(") + self.duration_time.strftime(
					f"{ESC_GREEN}%H{ESC_RES}:{ESC_GREEN}%M{ESC_RES}:{ESC_GREEN}%S{ESC_RES})"
				)
		)
	def set_paused(self, paused):
		self._paused = paused
	def set_errored(self, value):
		self._errored = value
		self._format()
	@property
	def description(self):
		if self._description is None:
			self._format()
		return self._description
	def __str__(self):
		if self._selected:
			self._format()
		return self.description
	@property
	def selected(self):
		return self._selected
	@selected.setter
	def selected(self, selected):
		self._selected = selected
		self._format()
	@property
	def index(self):
		return self._index
	@index.setter
	def index(self, index):
		self._index = index
		self._format()

# thread for dispacting queue print
class QueueTextPrinting(threading.Thread):
	_instance = None
	def __init__(self):
		super().__init__(daemon=True)
		self._event_loop = asyncio.new_event_loop()
	def run(self):
		print("run")
		asyncio.set_event_loop(self._event_loop)
		self._event_loop.run_forever()
		print("runned")
	def stop(self):
		self._event_loop.stop()
	def add_job(self, coroutine):
		return asyncio.run_coroutine_threadsafe(coroutine, loop=self._event_loop)
	@property
	def loop(self):
		return self._event_loop
	@classproperty
	def instance(cls):
		if cls._instance is None:
			cls._instance = QueueTextPrinting()
			cls._instance.start()
		return cls._instance

loop_names = ["выкл", "очередь", "текущее"]
	
class QueueViewController(disnake.ui.View):
	def __init__(self, queue_controller, interaction, indent=10, timeout=None):
		super().__init__(timeout=timeout)
		self._queue_controller = queue_controller
		self._interaction = interaction
		type(self)._indent = SharedOptions.instance.ctx_getter("default_queue_cut")

		self._print_start_index = 0
		self._text_printing = QueueTextPrinting.instance
		self._formatted_text = ""
		self._prev_selected_item = None
		self._items = []
		self._current_index = 0
		self._is_unsorted = False

		self._buttons = {}
		if True:
			self._prepare_extended_ui()
		else:
			self._prepare_default_ui()

		#self._enter_index_modal.callback = self.index_modal_sumbited
	def _add_button(self, callback, key, *args, **kvargs):
		button = disnake.ui.Button(*args, **kvargs)
		button.callback = callback
		self.add_item(button)
		self._buttons[key] = button
	def _get_button(self, key):
		return self._buttons.get(key)
	def _prepare_default_ui(self):
		self._add_button(callback=self.first_button_clicked, key="first", label="начало", style=disnake.ButtonStyle.primary, row=0)
		self._add_button(callback=self.prev_button_clicked, key="prev", label="пред", style=disnake.ButtonStyle.secondary, row=0)
		self._add_button(callback=self.index_button_clicked, key="index", label="перейти к", style=disnake.ButtonStyle.primary, row=0)
		self._add_button(callback=self.next_button_clicked, key="next", label="след", style=disnake.ButtonStyle.secondary, row=0)
		self._add_button(callback=self.last_button_clicked, key="last", label="конец", style=disnake.ButtonStyle.primary, row=0)

		self._add_button(callback=self.prev_item_button_clicked, key="prev_item", emoji="⬆️", style=disnake.ButtonStyle.secondary, row=1)
		self._add_button(callback=self.jump_button_clicked, key="jump", label="перейти к", style=disnake.ButtonStyle.primary, row=1)
		self._add_button(callback=self.next_item_button_clicked, key="next_item", emoji="⬇️", style=disnake.ButtonStyle.secondary, row=1)
		self._add_button(callback=self.add_item_button_clicked, key="add_item", label="добавить", style=disnake.ButtonStyle.success, row=1)
		self._add_button(callback=self.clear_button_clicked, key="clear", label="очистить", style=disnake.ButtonStyle.danger, row=1)

		self._add_button(callback=self.refresh_button_clicked, key="refresh", label="обновить", style=disnake.ButtonStyle.primary, row=2)

		index_input = disnake.ui.TextInput(label="index", custom_id="index", placeholder="0")
		self._enter_index_modal = CustomModal(callback=self.index_modal_sumbited, title="enter index", components=index_input)

		disnake.ui.TextInput(label="index", custom_id="index", placeholder="0")
		self._jump_modal = CustomModal(callback=self.jump_modal_sumbited, title="jump to item", components=index_input)

		url_input = disnake.ui.TextInput(label="url", custom_id="url")
		self._add_item_modal = CustomModal(callback=self.add_item_modal_sumbited, title="add item", components=url_input)
	def _prepare_extended_ui(self):
		#
		self._add_button(callback=self.jump_button_clicked, key="jump", emoji="<:goto_item_w:1188185007735451669>", style=disnake.ButtonStyle.secondary, row=0)
		self._add_button(callback=self.prev_item_button_clicked, key="prev_item", emoji="<:previous_w:1047993525859528724>", style=disnake.ButtonStyle.primary, row=0)
		self._add_button(callback=self.refresh_button_clicked, key="refresh", emoji="<:refresh:1047971541343805530>", style=disnake.ButtonStyle.secondary, row=0)
		self._add_button(callback=self.empty_button_clicked, key="empty0", label="឵", style=disnake.ButtonStyle.secondary, row=0)
		self._add_button(callback=self.prev_button_clicked, key="prev", emoji="⬆️", style=disnake.ButtonStyle.primary, row=0)

		#
		self._add_button(callback=self.backward_button_clicked, key="backward", emoji="<:backward_15_s_w:1047951395397046342>", style=disnake.ButtonStyle.primary, row=1)
		self._add_button(callback=self.play_pause_button_clicked, key="play_pause", emoji="<:pause_w:1047969045594513438>", style=disnake.ButtonStyle.secondary, row=1)
		self._add_button(callback=self.forward_button_clicked, key="forward", emoji="<:forward_15_s_w:1047969050896109649>", style=disnake.ButtonStyle.primary, row=1)
		self._add_button(callback=self.empty_button_clicked, key="empty1", label="឵", style=disnake.ButtonStyle.secondary, row=1)
		self._add_button(callback=self.index_button_clicked, key="index", emoji="↕️", style=disnake.ButtonStyle.primary, row=1)

		#
		self._add_button(callback=self.add_item_button_clicked, key="add_item", emoji="<:add:1047970470730940426>", style=disnake.ButtonStyle.secondary, row=2)
		self._add_button(callback=self.next_item_button_clicked, key="next_item", emoji="<:next_w:1047993514828505210>", style=disnake.ButtonStyle.primary, row=2)
		self._add_button(callback=self.remove_item_button_clicked, key="remove", emoji="<:remove:1047970467199328396>", style=disnake.ButtonStyle.secondary, row=2)
		self._add_button(callback=self.empty_button_clicked, key="empty2", label="឵", style=disnake.ButtonStyle.secondary, row=2)
		self._add_button(callback=self.next_button_clicked, key="next", emoji="⬇️", style=disnake.ButtonStyle.primary, row=2)

		#
		self._add_button(callback=self.repeat_button_clicked, key="repeat", emoji="🔁", style=disnake.ButtonStyle.secondary, row=3)
		self._add_button(callback=self.empty_button_clicked, key="empty3", label="឵", style=disnake.ButtonStyle.secondary, row=3)
		self._add_button(callback=self.shuffle_button_clicked, key="shuffle", emoji="🔀", style=disnake.ButtonStyle.secondary, row=3)

		# misc modals
		index_input = disnake.ui.TextInput(label="index", custom_id="index", placeholder="0")
		self._enter_index_modal = CustomModal(callback=self.index_modal_sumbited, title="enter index", components=index_input)
		self._jump_modal = CustomModal(callback=self.jump_modal_sumbited, title="jump to item", components=index_input)
		self._remove_item_modal = CustomModal(callback=self.remove_item_modal_sumbited, title="remove item", components=index_input)

		url_input = disnake.ui.TextInput(label="url", custom_id="url")
		self._add_item_modal = CustomModal(callback=self.add_item_modal_sumbited, title="add item", components=url_input)
	def echo(self):
		# self._text_printing.add_job(self._interaction.edit_original_response(content=self._formatted_text, view=self)).result()
		self._client.loop.create_task(self.aecho())
	async def aecho(self):
		if  self._interaction.is_expired():
			return
		if len(self._formatted_text) > 2000:
			await self._interaction.edit_original_message(content="`Error: Queue content characters greater than 2000`", view=self)
			return
		await self._interaction.edit_original_message(content=self._formatted_text, view=self)
	def _make_overall_duration(self):
		return HourlessTime(seconds=sum(map(lambda i: i.duration, self._items))).strftime(
			f"({ESC_GREEN}%H{ESC_RES}:{ESC_GREEN}%M{ESC_RES}:{ESC_GREEN}%S{ESC_RES})"
		)
	def format(self):
		current_index = self._queue_controller._current_index
		common_text = str((
			#"Информация\n"
			"```ansi\n"
			f"количество - {len(self._items)}, длительность - {self._make_overall_duration()}, повтор - {loop_names[self._queue_controller._loop]}\n"
			"```"
			#"Очередь\n"
			"```ansi\n"
			"{items} "
			"\n```"
		))
		print_items = []
		if current_index < self._print_start_index:
			print_items.append(self._items[current_index])
			print_items.append("...")
		print_items += self._items[self._print_start_index:self._print_start_index + self._indent]
		if current_index >= self._print_start_index + self._indent:
			print_items.append("...")
			print_items.append(self._items[current_index])
		self._formatted_text = common_text.format(items="\n".join(map(str, print_items)))
	async def update_interaction(self, interaction, delete=True):
		# if delete and self._interaction is not None and self._interaction != interaction:
			# await self._interaction.delete_original_response()
		self._interaction = interaction
		self.echo()
	def update(self):
		self.format()
		self.echo()
	# async versions
	async def aupdate(self):
		self.format()
		await self.aecho()
	def add(self, name, duration, no_refresh=False):
		self._items.append(Item(self._queue_controller, len(self._items), name, duration))
		if not no_refresh:
			self.update()
	def removed(self, slc, deleted, autorefresh=True):
		del self._items[slc]
		start = slc.start if slc.start else 0
		for i, item in enumerate(self._items[start:], start=start):
			item.index = i
		self._print_start_index = max(0, self._print_start_index - deleted)
		if autorefresh:
			self.update()
	def select(self, index):
		if self._prev_selected_item is not None:
			self._prev_selected_item.selected = False
		self._items[index].selected = True
		self._prev_selected_item = self._items[index]
	def deselect(self):
		if self._prev_selected_item is not None:
			self._prev_selected_item.selected = False
	def get_view_index(self):
		return self._print_start_index
	def get_current_item(self):
		return self._prev_selected_item
	def set_view_index(self, index):
		self._print_start_index = max(0, min(index, len(self._items)))
	def set_paused(self, paused):
		self._prev_selected_item.set_paused(paused)
		play_pause_button = self._get_button("play_pause")
		if play_pause_button:
			if not paused: # playing
				play_pause_button.emoji = "<:pause_w:1047969045594513438>"
			else:
				play_pause_button.emoji = "<:play_w:1047969044126515220>"
	def clear(self):
		self._items.clear()
	def set_errored(self, index, value):
		self._items[index].set_errored(value)
	def enum_items(self):
		return map(lambda v: (v.name, v.duration), self._items)

	async def first_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		self._print_start_index = 0
		await self.aupdate()
	async def prev_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		self._print_start_index = max(self._print_start_index - self._indent, 0)
		await self.aupdate()
	async def index_button_clicked(self, interaction):
		await interaction.response.send_modal(modal=self._enter_index_modal)
	async def next_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		self._print_start_index = min(self._print_start_index + self._indent, max(len(self._items) - self._indent, 0))
		await self.aupdate()
	async def last_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		self._print_start_index = len(self._items) - self._indent
		await self.aupdate()

	async def prev_item_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		self._queue_controller.previous()
	async def jump_button_clicked(self, interaction):
		await interaction.response.send_modal(self._jump_modal)
	async def next_item_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		self._queue_controller.next()
	async def add_item_button_clicked(self, interaction):
		await interaction.response.send_modal(self._add_item_modal)
	async def clear_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		self._queue_controller.clear()
		await self.aupdate()

	async def refresh_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		await self.update_interaction(interaction)
		await self.aupdate()
	async def repeat_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		loop = self._queue_controller.toggle_loop()
		repeat_button = self._get_button("repeat")
		if loop == 0:
			repeat_button.emoji = "🔁"
			repeat_button.style = disnake.ButtonStyle.secondary
		elif loop == 1:
			repeat_button.style = disnake.ButtonStyle.primary
		else:
			repeat_button.emoji = "🔂"

		await self.aupdate()
	async def shuffle_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		shuffle_button = self._get_button("shuffle")
		if self._queue_controller.toggle_shuffle():
			shuffle_button.style = disnake.ButtonStyle.primary
		else:
			shuffle_button.style = disnake.ButtonStyle.secondary
		await self.aupdate()
	async def remove_item_button_clicked(self, interaction):
		await interaction.response.send_modal(self._remove_item_modal)
	async def backward_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		if self._prev_selected_item:
			self._queue_controller.audio_time_set(RelativeTime(operation="-", seconds=15))
	async def forward_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		if self._prev_selected_item:
			self._queue_controller.audio_time_set(RelativeTime(operation="+", seconds=15))
	async def play_pause_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)
		self._queue_controller.play_pause()
		await self.aupdate()
	async def empty_button_clicked(self, interaction):
		await interaction.response.defer(with_message=False)

	async def index_modal_sumbited(self, interaction):
		await interaction.response.defer(with_message=False)
		index = interaction.text_values["index"]
		if index.isnumeric():
			index = int(index) - 1
		else:
			index = 0
		self._print_start_index = max(0, min(len(self._items) - self._indent, index))
		await self.aupdate()
	async def jump_modal_sumbited(self, interaction):
		await interaction.response.defer(with_message=False)
		index = interaction.text_values["index"]
		if index.isnumeric():
			index = int(index) - 1
		else:
			index = 0
		self._queue_controller.jump(index)
	async def add_item_modal_sumbited(self, interaction):
		await interaction.response.defer(with_message=False)
		await DownloadDispatcher.instance.download(interaction.text_values["url"], self._queue_controller, interaction)
	async def remove_item_modal_sumbited(self, interaction):
		await interaction.response.defer(with_message=False)
		index = interaction.text_values["index"] # not zero aligned
		if index.isnumeric():
			index = slice(int(index) - 1, int(index))
		elif index == "*":
			# self._queue_controller.clear()
			# self.update()
			# return
			index = slice(None, None)
		elif match := re.match(r"(?P<start>\d+)?\-(?P<end>\d+)?", index):
			match_dict = match.groupdict()
			start = match_dict.get("start")
			if isinstance(start, str):
				start = int(start)
			end = match_dict.get("end")
			if isinstance(end, str):
				end = int(end)

			if start is None:
				index = slice(start, end)
			else:
				index = slice(start - 1, end)
		else:
			index = slice(0, 1)

		self._queue_controller.remove(index, autorefresh=False)
		await self.aupdate()
		
FFMPEG_OPTIONS_DEFAULT = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 20', 'options': '-vn'}
# FFMPEG_OPTIONS_DEFAULT = {'before_options': '-stream_loop -1', 'options': '-vn'}

import re
scrool_check_re = re.compile("\d\d:\d\d:\d\d")

def slice_len_old(slc, max_size=None):
	start = slc.start
	if max_size is not None:
		if slc.stop is None:
			out = max(0, max_size - slc.start)
		else:
			out = max(0, min(max_size, slc.stop) - slc.start)
	else:
		if slc.stop is None:
			return -1
		out = max(0, slc.stop - (slc.start if slc.start else 0))
	if slc.step:
		out -= 1
		out //= slc.step
		out += 1
	return out

def slice_len(slc, max_size=None):
	start = slc.start if slc.start else 0
	if max_size is not None:
		stop = min(max_size, slc.stop) if slc.stop else max_size
		out = max(0, stop - start)
	else:
		if slc.stop is None:
			return -1
		out = max(0, slc.stop - start)

	if slc.step:
		out = math.ceil(out / slc.step)
	return out


def get_eq_option(freq, gain):
	return f"equalizer=f={freq}:width_type=o:width=1:g={gain}"

DEFAULT_GAINS = [
	(31, -3),
	(63, 3),
	(125, 6),
	(250, 2),
	(500, -3.5),
	(1000, -1.8),
	(2000, 1.8),
	(4000, 3),
	(8000, 5),
	(16000, 8)
]


class QueueController:
	@classmethod
	def bind_client(cls, client):
		QueueViewController._client = client
	def __init__(self, chat, voice, interaction, indent=10, timeout=None):
		self._chat = chat
		self._voice = voice
		self._view_controller = QueueViewController(self, interaction, indent, timeout)

		self._url = None
		self._items = [] # list of urls
		self._loop = 0
		self._force_stopped = False
		self._current_index = 0
		self._shared_options = SharedOptions.instance
		self._ffmpeg_options = FFMPEG_OPTIONS_DEFAULT.copy()
		self._goto_time = 0
		self._equalizer_options = self.set_equa_options(map(lambda v: v[1], DEFAULT_GAINS), 0)

		self._current_volume = 1.0

		self._shuffle = False
		self._audio_filter = "none"

		self._play_start_time = 0
		self._pause_start_time = 0

		# test
		self._cache_urls = {} # dict(url, time)
		self._cache_expire_time = 5 * 60 # seconds
	@property
	def ended(self):
		return self._voice is None or not self._voice.is_connected() or not self._voice.is_playing()
	@property
	def connected(self):
		return self._voice is not None and self._voice.is_connected()
	@property
	def playing(self):
		return self._voice is not None and self._voice.is_playing()
	@property
	def paused(self):
		return self._voice is not None and self._voice.is_paused()

	async def reconnect(self, autoplay=False):
		# await self._voice.connect(reconnect=False, timeout=-1)
		# if not self.connected:
		# 	self._voice = await self._voice.channel.connect()
		if self.connected:
			await self._voice.disconnect()
		self._voice = await self._chat.connect()
		if autoplay:
			self.play(replay=False)
			
	def _disable_play_callback(self):
		self._voice._player.after = None
	
	def toggle_loop(self):
		if self._loop == 2:
			self._loop = 0
		else:
			self._loop += 1
		self._view_controller.update()
		return self._loop
	async def update_interaction(self, interaction, delete=True):
		await self._view_controller.update_interaction(interaction, delete=delete)
	def echo(self):
		self._view_controller.echo()
	def refresh(self):
		self._view_controller.update()
	def add(self, url, name, duration, no_refresh=False):
		self._items.append(url)
		self._view_controller.add(name, duration, no_refresh=no_refresh)
	def insert(self, url, name, duration, index):
		self._items.insert(index, url)
		self._view_controller.insert(name, duration, index)
	def remove(self, slc, autorefresh=True):
		if isinstance(slc, int):
			slc = slice(slc, slc + 1)
		del self._items[slc]
		deleted = slice_len(slc, self._current_index)
		self._current_index = max(0, self._current_index - deleted)
		self._view_controller.removed(slc, deleted, autorefresh=autorefresh)
		return True
	def clear(self):
		self.stop()
		self._view_controller.clear()
		self._current_index = 0
		self._items.clear()
	def set_volume(self, volume):
		self._current_volume = volume
		self._voice.source.volume = volume
	def set_voice(self, voice):
		self._voice = voice
	def enum_urls(self):
		return self._items
	def enum_view_items(self):
		return self._view_controller.enum_items()
	def update_play_options(self, skip_time = 0, scroll="00:00:00", eq=False):
		self._ffmpeg_options = FFMPEG_OPTIONS_DEFAULT.copy()
		self._goto_time = skip_time
		default_af = self._shared_options.get("default_af").value
		self._ffmpeg_options['before_options'] += f" -ss {scroll}" + " " + (default_af if default_af != "none" else "")
		if eq:
			self._ffmpeg_options['options'] += f' -af "{self._equalizer_options}"'
		self._ffmpeg_options['options'] += f' -af "{self._audio_filter}"' if self._audio_filter != "none" else ""
		print(self._ffmpeg_options["options"])

	def audio_time_set(self, time: Union[HourlessTime, RelativeTime]):
		if isinstance(time, RelativeTime):
			gt_time = time.apply_rel(self.get_played_time())
		elif isinstance(time, HourlessTime):
			gt_time = time
		else:
			raise TypeError(f"Expected HourlessTime or RelativeTime, got {repr(time)}")
		self.update_play_options(skip_time = gt_time.total_seconds(), scroll=time_to_iso(gt_time))
		self.play(replay=True, replay_url=True)
		return self.get_played_time()
	def get_played_time(self):
		if self.paused:
			return self._goto_time + max(0, self._pause_start_time - self._play_start_time)
		else:
			return self._goto_time + max(0, perf_counter() - self._play_start_time)
	def get_current_index(self):
		return self._current_index
	def get_af_opts(self):
		return self._audio_filter

	def play_pause(self):
		if self.playing:
			self._view_controller.set_paused(True)
			self.pause()
			return True
		else:
			self._view_controller.set_paused(False)
			self.play(replay=False)
			return False
	def jump(self, index):
		if index < 0 or index >= len(self._items):
			return False
		self._current_index = index
		self.update_play_options()
		self.play(replay=True)
		return True
	def previous(self):
		if self._current_index <= 0:
			self._current_index = len(self._items) - 1
		else:
			self._current_index -= 1
		self.update_play_options()
		self.play()
		return True
	def next(self):
		if self._current_index >= len(self._items) - 1:
			self._current_index = 0
		else:
			self._current_index += 1
		self.update_play_options()
		self.play()
	def enable_equa(self):
		scroll = seconds_to_iso(self.get_played_time())
		self.update_play_options(scroll=scroll, eq=True)
		self.play(replay_url=True)
	def set_equa_options(self, gains, volume):
		_real_gains = zip([31, 63, 125, 250, 500, 1000, 2000, 4000, 8000], gains)
		self._equalizer_options = ",".join(map(lambda v: get_eq_option(*v), _real_gains)) + f",volume={volume}dB"
	def toggle_shuffle(self):
		self._shuffle = not self._shuffle
		return self._shuffle
	def set_audio_filter(self, audio_filter):
		self._audio_filter = audio_filter
	def _next(self, error=None, reconnect=True):
		if not self.connected and reconnect:
			task = self._view_controller._client.loop.create_task(self.reconnect(autoplay=True))
			return False
		if self.playing:
			self.stop()

		if self._shuffle:
			self._current_index = random.randint(0, len(self._items) - 1)

		elif (self._loop <= 1) and self._current_index >= len(self._items) - 1:
			if self._shared_options.get("auto_queue_clear"):
				self._items.clear()
				self._view_controller.clear()
			self._current_index = 0
			if self._loop == 0:
				self._view_controller.deselect()
				self._view_controller.update()
				return
		elif self._loop != 2:
			self._current_index += 1
			self._view_controller.select(self._current_index)

		self.update_play_options()
		self.play()

	def stop(self):
		if self.ended:
			return False
		self._disable_play_callback()
		self._voice.stop()
		return True
	def pause(self):
		if not self.connected:
			return False
		self._voice.pause()
		self._pause_start_time = perf_counter()
	def resume(self):
		if not self.connected:
			return False
		self._voice.resume()
		self._play_start_time += perf_counter() - self._pause_start_time
		self._pause_start_time = 0
	def play(self, replay=True, replay_url=False):
		print("play", self.connected)
		if not self.connected:
			task = self._view_controller._client.loop.create_task(self.reconnect(autoplay=True))
			return
		if self.playing:
			if not replay:
				return
			self.stop()

		if self.paused and not replay:
			print('resume')
			self.resume()
		else:
			# play
			if not (self._url and replay_url):
				if self._current_index >= len(self._items):
					print(self._items)
					raise Exception(f"current index exceeds length of items")
				try:
					if self._current_index in self._cache_urls and (perf_counter() - self._cache_urls[self._current_index]["time"]) <= self._cache_expire_time:
						self._url = self._cache_urls[self._current_index]["url"]
					else:
						self._url = DownloadDispatcher.instance.get_url(self._items[self._current_index])
					self._cache_urls[self._current_index] = {"url": self._url, "time": perf_counter()}
				except DownloaderError:
					self._view_controller.set_errored(self._current_index, True)
					if self._current_index + 1 >= len(self._items):
						self._current_index = 0
					else:
						self._current_index += 1
						self.play(replay=False)
					return
				else:
					self._view_controller.set_errored(self._current_index, False)
			before_opts = self._ffmpeg_options["before_options"]
			# vk fix
			if "vk.com" in self._url:
				before_opts += " -http_persistent false"
			source = disnake.PCMVolumeTransformer(
				disnake.FFmpegPCMAudio(
					source = self._url,
					before_options=before_opts, 
					options = self._ffmpeg_options["options"]
				),
				self._current_volume
			)

			self._voice.play(source, after = lambda e: self._next(e))
			self._play_start_time = perf_counter()

			self._view_controller.select(self._current_index)
			self._view_controller.set_paused(False)
		self._view_controller.update()

		# test
		if self._current_index > 0                    and self._current_index - 1 not in self._cache_urls:
			self._cache_urls[self._current_index - 1] = {"url": DownloadDispatcher.instance.get_url(self._items[self._current_index - 1]), "time": perf_counter()}
		if self._current_index < len(self._items) - 1 and self._current_index + 1 not in self._cache_urls:
			self._cache_urls[self._current_index + 1] = {"url": DownloadDispatcher.instance.get_url(self._items[self._current_index + 1]), "time": perf_counter()}
	
