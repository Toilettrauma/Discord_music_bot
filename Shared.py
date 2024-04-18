import disnake
from misc import classproperty

class Option:
	def __init__(self, name, description, default_value, cast_fn=None):
		self.name = name
		self.description = description
		self.value = default_value
		self.cast_fn = cast_fn
		self.type = type(default_value)
		self.completer = None
	def __bool__(self):
		return self.value
	def value_from_string(self, string):
		if self.cast_fn is not None:
			self.value = self.cast_fn(string, to_string=False)
		# default cast
		elif self.type is str:
			self.value = string
		else:
			self.value = self.type(int(string))
		self.call_completer()
	def value_to_string(self):
		if self.cast_fn is not None:
			return self.cast_fn(string, to_string=True)
		# default cast
		elif self.type is str:
			return self.value
		else:
			return int(self.value)
	def call_completer(self):
		if self.completer:
			self.completer(self.value)

class SharedOptions:
	_instance = None
	def __init__(self):
		self.options = dict()
		self.add_option(Option("auto_queue_clear", "Automatically clear queue after playing all (except loop)", False))
		self.add_option(Option("dj_role_enable", "Enable dj role. @everyone can only add to queue. Enable /setdj and /removedj commands", False))
		self.add_option(Option("default_af", "Sets default audio filter for audio", ""))
		self.add_option(Option("default_queue_cut", "Test queue setting", 10))

		self.load()
	def add_option(self, option):
		if self.options.get(option.name) is not None:
			print(f"Setings error: Option '{option.name} already exists")
			return
		self.options[option.name] = option
	def save(self):
		with open("options.txt", "w") as f:
			f.write("\n".join(map(lambda opt: f"{opt.name}:{opt.value_to_string()}", self.enum())))
	def load(self):
		with open("options.txt", "r") as f:
			to_set_options = self.options.copy()
			for line in f:
				line = line.rstrip()
				name, value = line.split(":", 1)
				option = self.options.get(name)
				if option is None:
					print(f"Error: option '{name}' not found.")
					continue
				del to_set_options[name]
				option.value_from_string(value)

			for option in to_set_options.values():
				print(f"Warning: option '{option.name}' not found in settings file, using default value")
	#
	def get(self, name):
		return self.options.get(name)
	def set(self, name, value):
		self.options[name].value = value
		self.save()
	def set_option_completer(self, name, completer):
		self.options[name].completer = completer
	#
	def enum(self):
		return self.options.values()
	def enum_names(self):
		return self.options.keys()
	def enum_items(self):
		return self.options.items()
	#
	class OptionGetter:
		def __init__(self, option):
			self.option = option
		def __get__(self, instance, owner):
			return self.option.value

	def ctx_getter(self, name):
		return self.OptionGetter(self.options[name])
	#
	@staticmethod
	def shared_instance():
		return SharedOptions.instance
	@classproperty
	def instance(cls):
		if cls._instance is None:
			cls._instance = SharedOptions()
		return cls._instance

class SharedSavedQueue:
	_instance = None