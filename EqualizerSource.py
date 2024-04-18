from disnake.player import AudioSource
from disnake.errors import ClientException
import numpy as np
from scipy import fftpack
import array
from typing import Tuple

import importlib
import StapleEqlzr
importlib.reload(StapleEqlzr)
from StapleEqlzr import *

def pcm_to_array(pcm : bytes) -> np.ndarray:
	ret_pcm = np.frombuffer(pcm, dtype="(4,)i1") # b"l1l2h1h2" -> [[l1, l2, h1, h2]]
	ret_pcm = ret_pcm[:,[0, 2, 1, 3]] # [[l1, l2, h1, h2]] -> [[l1, h1, l2, h2]]
	ret_pcm = ret_pcm.ravel() # [[l1, h1, l2, h2]] -> [l1, h1, l2, h2]
	ret_pcm = ret_pcm.view("i2") # [l1, h1, l2, h2] -> [u1, u2]
	ret_pcm = ret_pcm.reshape(-1, 2) #  [u1, u2] -> [[u1, u2]]
	return ret_pcm
def equalize_array(samples : np.ndarray, sample_rate : int, gains : list) -> np.ndarray:
	#frequency_content = np.fft.rfftfreq(len(samples), d=1 / sample_rate)
	modified_signal = np.fft.rfft(samples)
	for frame_index in range(0, len(samples), sample_rate // 1000 * 50):
		frequency_content = fftpack.rfftfreq(min(sample_rate // 1000 * 50, len(samples)), d=1 / sample_rate)
		for index, gain in enumerate(gains):
			# frequency_range_min = sample_rate / 1500 * (2 ** index)
			# frequency_range_max = sample_rate / 1500 * (2 ** index + 1)
			frequency_range_min = (index + 0) * sample_rate / (2 * 10)
			frequency_range_max = (index + 1) * sample_rate / (2 * 10)
			range_min_frequency = frequency_content > frequency_range_min
			range_max_frequency = frequency_content <= frequency_range_max
			content_min_max = [in_min and in_max for in_min, in_max in zip(range_min_frequency, range_max_frequency)]
			modified_signal[frame_index : frame_index + sample_rate // 1000 * 50][content_min_max] *= gain
	samples_after = np.fft.irfft(modified_signal).astype(np.int16)
	return samples_after
def array_to_pcm(samples : np.ndarray):
	ret_pcm = samples.ravel() # [[u1, u2]] -> [u1, u2]
	ret_pcm = ret_pcm.view("i1") # [u1, u2] -> [l1, h1, l2, h2]
	ret_pcm = ret_pcm.reshape(-1, 4) # [l1, h1, l2, h2] -> [[l1, h1, l2, h2]]
	ret_pcm = ret_pcm[:,[0, 2, 1, 3]] # [[l1, h1, l2, h2]] -> [[l1, l2, h1, h2]]
	#ret_pcm = ret_pcm.ravel() # [[l1, l2, h1, h2]] -> [l1, l2, h1, h2]
	ret_pcm = ret_pcm.tobytes() # [l1, l2, h1, h2] -> b"l1l2h1h2"
	return ret_pcm

def pcm_to_array2(pcm : bytes) -> Tuple[array.array, array.array]:
	ret_pcm = np.frombuffer(pcm, dtype="(4,)i1") # b"l1l2h1h2" -> [[l1, l2, h1, h2]]
	ret_pcm = ret_pcm[:,[0, 2, 1, 3]] # [[l1, l2, h1, h2]] -> [[l1, h1, l2, h2]]
	ret_pcm = ret_pcm.ravel() # [[l1, h1, l2, h2]] -> [l1, h1, l2, h2]
	ret_pcm = ret_pcm.view("i2") # [l1, h1, l2, h2] -> [u1, u2]
	ret_pcm_left = ret_pcm[::2] #  [u1, u2] -> [u1]
	ret_pcm_right = ret_pcm[1::2] # [u1, u2] -> [u2]
	return array.array("h", ret_pcm_left), array.array("h", ret_pcm_right)


def pcm_to_array_n(pcm : bytes) -> Tuple[array.array, array.array]:
	ret_arr = array.array("h", pcm) # b"l1r1l2r2" -> array('h', [l1, r1, l2, r2])
	ret_arr_left = ret_arr[::2] # array('h', [l1, r1, l2, r2]) -> array('h', [l1, l2])
	ret_arr_right = ret_arr[1::2] # array('h', [l1, r1, l2, r2]) -> array('h', [r1, r2])
	return ret_arr_left, ret_arr_right # (array('h', [l1, l2]), array('h', [r1, r2]))

def array_to_pcm_n(samples : Tuple[array.array, array.array]) -> bytes:
	return np.array(samples).T.tobytes() # (array('h', [l1, l2]), array('h', [r1, r2])) ->
										 # array([l1, l2, r1, r2]) -> 
										 # array([[l1, r1], [l2, r2]]) ->
										 # array([[l1, r1], [l2, r2]]) -> b"l1r1l2r2"


from scipy.io import wavfile as wav
def equalize_pcm(pcm : bytes) -> bytes:
	# load song as numeric array
	numeric_array = pcm_to_array_n(pcm)
	#print(numeric_array)

	eq = Equalizer()
	eq.setFilters()
	filterList = eq.getFilters()

	# change iteger value to select different presets (0:pop, 1:rock)
	g = Gain()
	g.loadGain()
	g.setGain(1)

	data = [0, 0]
	for arr_i in range(2):
		i = 0
		while i < len(filterList):
			data[arr_i] = data[arr_i] + np.multiply(g.getGain(i), np.convolve(filterList[i].getFiltVal(), numeric_array[arr_i]))
			i = i+1
	
	# save song
	# https://stackoverflow.com/questions/10357992/how-to-generate-audio-from-a-numpy-array
	#print(data)
	scaled_left = np.int16(data[0]/np.max(np.abs(data[0])) * 32767)
	scaled_right = np.int16(data[1]/np.max(np.abs(data[1])) * 32767)
	#print(scaled_right)
	
	wav.write("output.wav", 48000, np.array((scaled_left, scaled_right)).T)

	return array_to_pcm_n((scaled_left, scaled_right))
	
	# play song (I could merge everything in one function but I do not always want to play)
	# player.playSong(data2)

from disnake.opus import Encoder as OpusEncoder

class PCMVolumeEqualizer(AudioSource):
	def __init__(self, original : AudioSource, gains):
		"""
		original.read must return bytes with length multiple of 4
		"""
		if not isinstance(original, AudioSource):
			raise TypeError(f"expected AudioSource not {original.__class__.__name__}.")

		if original.is_opus():
			raise ClientException("AudioSource must not be Opus encoded.")

		if isinstance(gains, list) and len(gains) != 10:
			raise TypeError(f"expected gains of type list with length 10")
		self.original = original
		self.gains = gains
	def read(self) -> bytes:
		ret = self.original.read()
		real_ret = equalize_pcm(ret)
		print(len(real_ret))
		return real_ret
