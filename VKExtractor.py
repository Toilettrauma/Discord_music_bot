import requests
from youtube_dl.extractor.common import InfoExtractor
import json
import re
from VKLoginHelper import VKLoginHelper
from base64 import b64decode
import html
from datetime import datetime
from Secrets import vk_login_creds

"""
	audio payload

	0 -> audio id ?
	1 -> playlist user id
	2 -> audio url
	3 -> title
	4 -> author
	5 -> duration (in seconds)

"""

def current_date_str():
	return datetime.now().strftime("%D")

class VKAudioIE(InfoExtractor):
	_VALID_URL = r"https://(?:www\.)?vk\.com/(?:audio(?P<audio_id>[\d\w_]+)|music/playlist/(?P<playlist_id>[\d\w_]+))"
	_LOGIN_HELPER = None
	_LOGIN_TIME = None
	def __init__(self, *args, **kvargs):
		super().__init__(*args, **kvargs)
		if not self._LOGIN_HELPER:
			type(self)._LOGIN_HELPER = VKLoginHelper()
			self._custom_login()
	def _real_extract(self, url):
		if self._LOGIN_TIME != current_date_str():
			print("(VKExtractor) Relogin")
			self._custom_login()

		mobj = re.match(self._VALID_URL, url)
		audio_id = mobj.group("audio_id")

		if not audio_id:
			playlist_id = mobj.group("playlist_id")

			return self._extract_playlist(playlist_id)
		else:
			return self._extract_audio(audio_id)
	def _extract_audio(self, audio_id):
		audio_info = self.get_audio_info(audio_id)
		if not audio_info["url"]:
			# url empty. :\
			hls_url = "https://vk.com/mp3/audio_api_unavailable.mp3"
		else:
			hls_url = self.generate_index_url(audio_info["url"], audio_info["ads"]["vk_id"])

		return {
			"id" : audio_id,
			"title" : html.unescape(audio_info["title"]),
			"duration" : audio_info["duration"],
			"formats" : [
				{
					"asr" : 44100,
					"quality" : 0,
					"url" : hls_url,
					"ext" : "m3u8",
					"acodec" : "opus"
				}
			]
		}
	def _extract_playlist(self, playlist_id):
		audios_info = self.get_playlist_audios(playlist_id)
		# print(audios_info)
		audios_hls = map(lambda v: self._extract_audio(v["audio_raw_id"]), audios_info)

		return {
			"id" : playlist_id,
			"entries" : audios_hls
		}

	# -------------- generate index url from url with extra
	def generate_index_url(self, url, vk_id):
		# print(url, vk_id)
		extra, extra_hashtag = url.split("?extra=")[1].split("#")

		decoded_extra_hashtag = ""
		if extra_hashtag:
			decoded_extra_hashtag = self.decode_string(extra_hashtag)

		decoded_extra = self.decode_string(extra)
		if not decoded_extra:
			return url

		extra_hashtag_function, extra_hashtag_number = decoded_extra_hashtag.split(chr(11))
		functions = {
			"i" : self.make_index_url,
			"s" : self.decode_url
		}

		function = functions[extra_hashtag_function]
		return function(decoded_extra, extra_hashtag_number, vk_id)
	def make_index_url(self, decoded_extra, hashtag_number, vk_id):
		return self.decode_url(decoded_extra, int(hashtag_number) ^ vk_id)
	def decode_url(self, decoded_extra, xored_hashtag_number):
		decoded_extra_len = len(decoded_extra)
		if decoded_extra_len == 0:
			return decoded_extra

		decode_chars = [None] * decoded_extra_len
		decode_char = abs(xored_hashtag_number)
		for i in range(decoded_extra_len - 1, -1, -1):
			decode_char = (decoded_extra_len * (i + 1) ^ decode_char + i) % decoded_extra_len
			decode_chars[i] = decode_char

		chars = list(decoded_extra)
		for i in range(1, decoded_extra_len):
			# char = chars[decode_chars[decoded_extra_len - 1 - i]]
			# chars[decode_chars[decoded_extra_len - 1 - i]] = chars[i]
			# chars[i] = char

			replace_index = decode_chars[decoded_extra_len - 1 - i]
			chars[replace_index], chars[i] = chars[i], chars[replace_index]

		return "".join(chars)
	def decode_string(self, extra):
		if extra is None or len(extra) % 4 == 1:
			return ""
		charmap = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN0PQRSTUVWXYZO123456789+/=" # 0 and O are mixed up
		ret_string = ''
		for i, char in enumerate(extra):
			charmap_index = charmap.index(char)
			if i % 4 != 0:
				number = 64 * number + charmap_index
				ret_string += chr(255 & number >> (-2 * (i + 1) & 6))
			else:
				number = charmap_index

		return ret_string
	# --------------------------------------------------------- playlist

	def get_playlist_audios(self, playlist_id):
		payload = type(self)._LOGIN_HELPER.post("https://vk.com/al_audio.php?act=get_audio_ids_by_source", {
			"al" : "1",
			"context" : "",
			"playlist_id" : playlist_id
		})["payload"]

		return payload[1][0]

	# ---------------------------------------------------------- audio

	def get_audio_info(self, audio_id : str):
		payload = type(self)._LOGIN_HELPER.post("https://vk.com/al_audio.php?act=reload_audios", {
			"al" : "1",
			"audio_ids" : audio_id
		})["payload"]

		audio_info_tuple = payload[1][0][0]
		return self.audio_tuple_to_dict(audio_info_tuple)

	def audio_tuple_to_dict(self, audio_tuple):
		audio_indexes = [
			"id",
			"owner_id",
			"url",
			"title",
			"performer",
			"duration",
			"album_id",
			"unk",
			"author_link",
			"lyrics",
			"flags",
			"context",
			"extra",
			"hashes",
			"cover_url",
			"ads",
			"subtitle",
			"main_artists",
			"feat_artists",
			"album",
			"track_code",
			"restriction",
			"album_part",
			"unk2",
			"access_key",
			"chart_info",
			"track_page_id",
			"is_original_sound"
		]

		# out_dict = {}
		# for i, audio_index in enumerate(audio_indexes):
		# 	out_dict.update({audio_index : audio_tuple[i]})

		out_dict = dict(zip(audio_indexes, audio_tuple))

		return out_dict
	def _custom_login(self):
		type(self)._LOGIN_HELPER.login(vk_login_creds["username"], vk_login_creds["password"])
		type(self)._LOGIN_TIME = current_date_str()


# add youtube_dl compatibility
from youtube_dl import extractor
extractor._ALL_CLASSES.insert(-1, VKAudioIE) # add class
extractor.__dict__.update({"VKAudioIE":VKAudioIE}) # add clas to global