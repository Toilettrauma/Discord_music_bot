from threading import Thread
from youtube_dl import YoutubeDL, DownloadError
import youtube_dl
import asyncio
from time import sleep
import disnake
import re

from misc import classproperty
from Logger import Logger

import VKExtractor

YDL_OPTIONS = {'format': 'bestaudio', 'cookiefile' : 'cookies.txt', 'cachedir' : False, 'ignoreerrors' : True, "quiet":True, "verbose":True}
YDL_OPTIONS_VIDEO = {'cookiefile' : 'cookies.txt'}

import string, random
def gen_string(size=6, chars=string.ascii_uppercase + string.digits):
	return ''.join(random.choice(chars) for _ in range(size))

class DownloaderError(DownloadError): pass

class DownloadDispatcher(Thread):
	_instance = None
	_WORKERS_COUNT = 10
	def __init__(self):
		super().__init__(daemon=True)
		self._event_loop = asyncio.new_event_loop()
	async def _start(self, url, queue_controller, interaction, autoplay):
		with YoutubeDL(YDL_OPTIONS) as ydl:
			print("extract")
			preinfo = ydl.extract_info(url, process=False)
			if 'url' in preinfo:
				preinfo = ydl.extract_info(preinfo['url'], process=False)
			is_playlist = 'entries' in preinfo

			if is_playlist:
				for item in preinfo['entries']:
					queue_controller.add(f"https://www.youtube.com/watch?v={item['id']}", item['title'], item['duration'], no_refresh=True)
			else:
				queue_controller.add(preinfo['webpage_url'], preinfo['title'], preinfo['duration'], no_refresh=True)

		queue_controller.refresh()
		if autoplay:
			queue_controller.play(replay=False)
	async def _start_search(self, search_tag):
		with YoutubeDL(YDL_OPTIONS) as ydl:
			preinfo = ydl.extract_info(f"ytsearch25:{search_tag}", process=False)
			out = []
			for info in preinfo['entries']:
				out.append({"url":info['url'], "title":info['title'], "duration":info['duration']})
		return out
	def get_url(self, url):
		with YoutubeDL(YDL_OPTIONS) as ydl:
			# if re.match(r"\d{6,}_\d{8,}", v_id) is not None: # VKExtractor
			# 	info = ydl.extract_info(f"https://vk.com/audio{v_id}", process=False)["formats"][0]
			# else:
			# 	info_raw = ydl.extract_info(f"https://www.youtube.com/watch?v={v_id}", process=False)
			# 	selector = ydl.build_format_selector("bestaudio")
			# 	try:
			# 		info = next(selector(info_raw))
			# 	except StopIteration:
			# 		info = info_raw['formats'][0]
			info_raw = ydl.extract_info(url, process=False)
			if info_raw is None:
				print("Failed to extract")
				raise DownloaderError("Failed to extract info (Downloader.py)")
			selector = ydl.build_format_selector("bestaudio")
			try:
				info = next(selector(info_raw))
			except StopIteration:
				info = info_raw['formats'][0]
		return info['url']
	async def download(self, url, queue_controller, interaction, delete=True, autoplay=True):
		#asyncio.run_coroutine_threadsafe(self._start(url, queue_controller, interaction), self._event_loop)
		Logger.printline("info", "download")
		if url.startswith("http"):
			await self._start(url, queue_controller, interaction, autoplay)
			Logger.printline("play", url, interaction)
		else:
			await SearchViewController(await self._start_search(url), queue_controller, delete=delete).show(interaction)
			Logger.printline("play (search)", url, interaction)
	def run(self):
		asyncio.set_event_loop(self._event_loop)
		self._event_loop.run_forever()
	def stop(self):
		self._event_loop.stop()
	def close(self):
		self._event_loop.stop()
		sleep(0.2)
		self._event_loop.close()
	@classproperty
	def instance(cls):
		if cls._instance is None:
			cls._instance = cls()
			cls._instance.start()
		return cls._instance
	

class SearchViewController(disnake.ui.View):
	def __init__(self, search_entries, queue_controller, delete=True, timeout=30.0):
		super().__init__(timeout=timeout)
		self._entries = search_entries
		# self._entries = []
		# for i, entry in enumerate(search_entries):
		# 	title = entry["title"]
		# 	if title in self._entries:
		# 		title += "(%i)" % (self._entries[:i].count(title) + 1)
		# 	entry["title"] = title
		# 	self._entries.append(entry)
		# print(self._entries)
		self._queue_controller = queue_controller
		self._delete = False

		self._responsed = False
		self._interaction = None
		self._search_select = disnake.ui.StringSelect(custom_id="search", placeholder="select search entry", min_values=1, max_values=1, row=0)
		self._search_select.callback = self.callback
		for entry in search_entries:
			self._search_select.add_option(label=entry['title'], value=entry["url"])
		self.add_item(self._search_select)
	async def show(self, interaction):
		await interaction.send(content=" ", view=self, ephemeral=True)
		self._interaction = interaction
	async def callback(self, interaction):
		self._responsed = True
		await interaction.response.defer(with_message=False)
		value = interaction.values[0]
		# for entry in self._entries:
		# 	if entry['title'] == value:
		# 		self._queue_controller.add(*entry.values())
		# 		Logger.printline("play (id)", list(entry.values())[0])
		# 		self._queue_controller.play(replay=False)
		# 		if self._delete:
		# 			await self._interaction.delete_original_response()
		current_entry = None
		for entry in self._entries:
			if entry["url"] == value:
				current_entry = entry
				break
		else:
			return
		self._queue_controller.add(
			url=f"https://www.youtube.com/watch?v={current_entry['url']}",
			name=current_entry["title"],
			duration=current_entry["duration"]
		)
		Logger.printline("play (id)", value)
		self._queue_controller.play(replay=False)
	async def on_timeout(self):
		if self._delete and not self._responsed and self._interaction:
			self._interaction.delete_original_response()