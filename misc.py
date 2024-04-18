import inspect
from MutableTime import HourlessTime, RelativeTime
import re
from typing import Union

class classproperty(property):
	def __get__(self, cls, owner):
		return classmethod(self.fget).__get__(None, owner)()

def _instance_getter_old(*args, **kvargs):
	def decorator(cls):
		if isinstance(cls.__init__, type(object.__init__)) and (args or kvargs):
			# no custom constructor and arguments provided
			raise ValueError(f"Class {cls} don't have constructor and arguments are provided")
		return type(
			cls.__name__,
			(BaseSharedInstance,) + cls.__mro__[1:], # add class and remove cls from mro
			dict(**cls.__dict__, _SI_ARGS=(args, kvargs)) # add _SI_ARGS field to cls
		)
	return decorator

def instance_getter(*args, **kvargs):
	def decorator(cls):
		instance = cls(*args, **kvargs)
		return type(
			cls.__name__,
			cls.__mro__[:-1] + (BaseSharedInstance, object), # insert BaseSharedInstance before object
			dict(**cls.__dict__, SI_INSTANCE = instance) # add SI_INSTANCE field to cls
		)
	return decorator

def iso_to_seconds(iso_time):
	return HourlessTime.fromisoformat(iso_time).total_seconds()
def seconds_to_iso(seconds):
	return HourlessTime(seconds=seconds).strftime("%H:%M:%S")
def time_to_iso(time: HourlessTime):
	return time.strftime("%H:%M:%S")
def from_postfix_time(pf_time : str) -> Union[RelativeTime, HourlessTime]:
	match = re.match(r"(?P<prefix>\+|\-)?(?:(?P<hours>\d+)h)? ?(?:(?P<minutes>\d+)m)? ?(?:(?P<seconds>\d+)s)?", pf_time)
	if not match:
		return HourlessTime()
	matchdict = match.groupdict()
	pf, hh, mm, ss = matchdict.get("prefix"), int(matchdict.get("hours") or 0), int(matchdict.get("minutes") or 0), int(matchdict.get("seconds") or 0), 
	if pf:
		return RelativeTime(pf, seconds=ss, minutes=mm, hours=hh)
	else:
		return HourlessTime(seconds=ss, minutes=mm, hours=hh)
def relu(num):
	return max(0, num)

class _BaseSharedInstanceOld:
#	_SI_ARGS = ((), {})
	_SI_INSTANCE = None
	@classproperty
	def instance(cls):
		if cls._SI_INSTANCE is None:
			cls._SI_INSTANCE = cls(*cls._SI_ARGS[0], **cls._SI_ARGS[1])
		return cls._SI_INSTANCE

class BaseSharedInstance:
	# SI_INSTANCE = None
	@classproperty
	def instance(cls):
		return cls.SI_INSTANCE
