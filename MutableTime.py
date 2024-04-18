import re
from typing import Union, Literal
import operator

# milliseconds : range[0, 100]
# seconds : range[0, 59]
# minutes : range[0, 59]
# hours : range[0, ...]
# no floats, non negative operators
class HourlessTime:
	def __init__(self, milliseconds=0, seconds=0, minutes=0, hours=0):
		self._seconds, self._milliseconds = divmod(int(milliseconds), 100)
		self._minutes, self._seconds = divmod(int(self._seconds + seconds), 60)
		self._hours, self._minutes = divmod(int(self._minutes + minutes), 60)
		self._hours += hours
	def strftime(self, fmt):
		output_fmt = fmt.replace("%H", "{0:02d}")
		output_fmt = output_fmt.replace("%M", "{1:02d}")
		output_fmt = output_fmt.replace("%S", "{2:02d}")
		return output_fmt.format(self._hours, self._minutes, self._seconds)
	def total_seconds(self):
		return self._hours * 3600 + self._minutes * 60 + self._seconds # ignore ms
	# %[H+]H:[M]M[:[S]S[.[[m]m]m]]
	@staticmethod
	def fromisoformat(iso):
		mat = re.match(r"T?(?P<hours>\d+):(?P<minutes>[0-5]?[0-9])(?::(?P<seconds>[0-5]?[0-9])(?:\.(?P<milliseconds>[0-9]{1,3}))?)?$", iso)
		mat_dict = mat.groupdict()
		hh, mm, ss, ms = mat_dict.values()
		if not ss:
			ss = 0
		if not ms:
			ms = 0
		return HourlessTime(int(hh), int(mm), int(ss), int(ms))
	def toisoformat(self):
		return self.strftime("%H:%M:%S")
	def __str__(self):
		return "HourlessTime(milliseconds={0}, seconds={1}, minutes={2}, hours={3})".format(self._milliseconds, self._seconds, self._minutes, self._hours)

	# lazy
	def __add__(self, time: "HourlessTime") -> "HourlessTime":
		return HourlessTime(seconds=self.total_seconds() + time.total_seconds())
	def __sub__(self, time: "HourlessTime") -> "HourlessTime":
		return HourlessTime(seconds=max(0, self.total_seconds() - time.total_seconds()))

# non negative
class RelativeTime(HourlessTime):
	def __init__(self, operation : Literal["+", "-"], *args, **kvargs):
		operations = {
			"+": operator.add,
			"-": operator.sub
		}
		self.operation = operation
		self._operation_func = operations[operation]
		super().__init__(*args, **kvargs)
	def apply_rel(self, time: Union[HourlessTime, int, float]) -> HourlessTime:
		if isinstance(time, int) or isinstance(time, float):
			time = HourlessTime(seconds=time)
		return self._operation_func(time, self)

	def __str__(self):
		return "RelativeTime(op={0},milliseconds={1}, seconds={2}, minutes={3}, hours={4})".format(self.operation, self._milliseconds, self._seconds, self._minutes, self._hours)
