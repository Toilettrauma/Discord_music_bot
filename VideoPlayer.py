import disnake

import threading
import subprocess

from typing import *
import logging
import traceback
import time
import sys

CREATE_NO_WINDOW: int

if sys.platform != "win32":
	CREATE_NO_WINDOW = 0
else:
	CREATE_NO_WINDOW = 0x08000000

class VideoSource:
	def read(self) -> bytes:
		raise NotImplementedError
	def cleanup(self):
		pass
	def __del__(self):
		self.cleanup()

FFMPEG_FRAME_SIZE = 640 * 360 * 3

MISSING = None

_log = logging.getLogger(__name__)

class FFMpegVideo(VideoSource):
	def __init__(
		self,
		source: str,
		*,
		executable: str = "ffmpeg",
		before_options: Optional[str] = None,
		options: Optional[str] = None,
		**subprocess_kwargs: Any,
	):
		piping = subprocess_kwargs.get("stdin") == subprocess.PIPE
		if piping and isinstance(source, str):
			raise TypeError(
				"parameter conflict: 'source' parameter cannot be a string when piping to stdin"
			)

		args = [executable]
		if isinstance(before_options, str):
			args.extend(before_options.split(" "))

		
		args.append("-i")
		args.append(source)
		#args.extend(("-f", "s16le", "-ar", "48000", "-ac", "2", "-loglevel", "warning"))
		args.extend(("-f", "rawvideo", "-c:v", "rawvideo", "-pix_fmt", "rgb24", "-vf", "scale=640:360,fps=3", "-loglevel", "warning"))
		#args.extend(("-vf", "scale=640:360,fps=5", "-loglevel", "warning"))

		if isinstance(options, str):
			args.extend(options.split(" "))

		args.append("pipe:1")

		kwargs = {"stdout": subprocess.PIPE}
		kwargs.update(subprocess_kwargs)

		self._process: subprocess.Popen[bytes] = self._spawn_process(args, **kwargs)
		self._stdout: IO[bytes] = self._process.stdout  # type: ignore
		self._stdin: Optional[IO[bytes]] = None
		self._pipe_thread: Optional[threading.Thread] = None

		if piping:
			n = f"popen-stdin-writer:{id(self):#x}"
			self._stdin = self._process.stdin
			self._pipe_thread = threading.Thread(
				target=self._pipe_writer, args=(source,), daemon=True, name=n
			)
			self._pipe_thread.start()

	def _spawn_process(self, args, **subprocess_kwargs: Any):# -> subprocess.Popen[bytes]:
		try:
			return subprocess.Popen(args, creationflags=CREATE_NO_WINDOW, **subprocess_kwargs)  # type: ignore
		except FileNotFoundError:
			executable = args.partition(" ")[0] if isinstance(args, str) else args[0]
			raise ClientException(executable + " was not found.") from None
		except subprocess.SubprocessError as exc:
			raise ClientException(f"Popen failed: {exc.__class__.__name__}: {exc}") from exc
	def _kill_process(self) -> None:
		proc = self._process
		if proc is MISSING:
			return

		_log.info("Preparing to terminate ffmpeg process %s.", proc.pid)

		try:
			proc.kill()
		except Exception:
			_log.exception("Ignoring error attempting to kill ffmpeg process %s", proc.pid)

		if proc.poll() is None:
			_log.info("ffmpeg process %s has not terminated. Waiting to terminate...", proc.pid)
			proc.communicate()
			_log.info(
				"ffmpeg process %s should have terminated with a return code of %s.",
				proc.pid,
				proc.returncode,
			)
		else:
			_log.info(
				"ffmpeg process %s successfully terminated with return code of %s.",
				proc.pid,
				proc.returncode,
			)
	def read(self) -> bytes:
		"""
		Read one rbg24 frame
		"""
		ret = self._stdout.read(FFMPEG_FRAME_SIZE)
		if len(ret) != FFMPEG_FRAME_SIZE:
			return b""
		return ret

VideoClient = type

class VideoPlayer(threading.Thread):
	def __init__(self, 
		source: VideoSource, 
		client : VideoClient, 
		delay=0.5, # in seconds
		after=None
	):
		threading.Thread.__init__(self)
		self.daemon: bool = True
		self.source: VideoSource = source
		self.client: VideoClient = client
		self.delay = delay
		self.after: Optional[Callable[[Optional[Exception]], Any]] = after

		self._end: threading.Event = threading.Event()
		self._resumed: threading.Event = threading.Event()
		self._resumed.set()  # we are not paused
		self._current_error: Optional[Exception] = None
		self._lock: threading.Lock = threading.Lock()

		if after is not None and not callable(after):
			raise TypeError('Expected a callable for the "after" parameter.')
	def _do_run(self):
		send_frame = self.client.send_frame

		while not self._end.is_set():
			start_time = time.perf_counter()

			data = self.source.read()
			if not data:
				self.stop()
				break
			send_frame(data)

			delta = time.perf_counter() - start_time
			time.sleep(max(0, self.delay - delta))
	def run(self):
		try:
			self._do_run()
		except Exception as exc:
			self._current_error = exc
			self.stop()
		finally:
			self._call_after()
			self.source.cleanup()
	def _call_after(self):
		error = self._current_error

		if self.after is not None:
			try:
				self.after(error)
			except Exception as exc:
				_log.exception("Calling the after function failed.")
				exc.__context__ = error
				traceback.print_exception(type(exc), exc, exc.__traceback__)
		elif error:
			msg = f"Exception in voice thread {self.name}"
			_log.exception(msg, exc_info=error)
			print(msg, file=sys.stderr)
			traceback.print_exception(type(error), error, error.__traceback__)
	def stop(self) -> None:
		self._end.set()
		self._resumed.set()
	def force_stop(self) -> None:
		self.after = None
		self._end.set()
		self._resumed.set()

from PIL import Image
from io import BytesIO
import asyncio

test_event_loop = asyncio.new_event_loop()
def test_loop_main():
	test_event_loop.run_forever()
test_loop_thread = threading.Thread(target=test_loop_main, args=())
test_loop_thread.start()

class VideoClient:
	def __init__(self, output_message : disnake.abc.Messageable, event_loop):
		self.output_message = output_message
		self.event_loop = event_loop
		self._frame_skip_num = 0
		self._player = None
	def play(self, source, after=None, skip_rate=0):
		if self._player is not None:
			return
		self._player = VideoPlayer(source, self, after=after, delay=0.09)
		self._player.start()
		self._skip_rate = skip_rate
	def stop(self):
		self._player.stop()
		self._player = None
	def send_frame(self, frame):
		# if self._frame_skip_num < self._skip_rate:
		# 	self._frame_skip_num += 1
		# 	return
		# self._frame_skip_num = 0
		image = Image.frombytes("RGB", (640, 360), frame)
		image_png_data = BytesIO()
		image.save(image_png_data, format="jpeg")
		image_png_data.seek(0)

		image_file = disnake.File(image_png_data, filename="frame.jpeg")

		# self.event_loop.create_task(self.output_message.edit_original_message(file=image_file))
		asyncio.ensure_future(self.output_message.edit_original_message(file=image_file), loop=self.event_loop)