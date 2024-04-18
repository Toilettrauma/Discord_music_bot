import disnake
from Shared import SharedOptions
from misc import classproperty

class OptionsController(disnake.ui.View):
	def __init__(self, interaction=None, timeout=180.0, author=None):
		super().__init__(timeout=timeout)

		self.interaction = interaction
		self.author = author

		self.options_select_view = disnake.ui.Select()#min_values = 1, max_values = 25)
		self.shared_options = SharedOptions.shared_instance()
		for option in self.shared_options.enum():
			self.options_select_view.add_option(label=option.description, value=option.key, default=option.value)

		self.add_item(self.options_select_view)

		self.prev_values = self.options_select_view.values
	def update_interaction(self, interaction, set_author=True):
		self.interaction = interaction
		if set_author:
			self.author = self.interaction.author
	async def on_timeout(self):
		self.clear_items()
		if self.interaction is not None:
			await self.interaction.edit_original_message("Timed out", view=None)
	async def interaction_check(self, interaction):
		if self.author is not None:
			return self.author == interaction.author

	async def on_option_select(interaction):
		select_view = interaction.component
		options_controller = select_view.view
		shared = options_controller.shared_options
		
		# search disabled
		for value in select_view.values:
			if value not in options_controller.prev_values:
				shared_options.set(value, False)
				print("%s setted to False" % value)

		# search enabled
		for value in options_controller.prev_values:
			if value not in select_view.values:
				shared_options.set(value, True)
				print("%s setted to True" % value)


	async def send_options(self):
		if self.interaction is not None:
			await self.interaction.edit_original_message(view=self)

class RawOptionsController:
	_instance = None
	def __init__(self):
		self.shared_options = SharedOptions.shared_instance()
		self.cache_option = None
	@classproperty
	def instance(cls):
		if cls._instance is None:
			cls._instance = cls()
		return cls._instance

	def autocomplete_options(self, user_input):
		ret_options = []
		for option in self.shared_options.enum():
			if option.name.startswith(user_input):
				ret_options.append(option.name)
		return ret_options
	def autocomplete_option_value(self, name, user_input):
		option = self.shared_options.get(name)
		if option is None:
			return ["INVALID OPTION"]
		if user_input != "":
			return []
		if option.type is bool:
			return ["%s (current)" % option.value, "%s" % (not option.value)]
		return ["%s (current)" % option.value]

	def set(self, option_name, option_value):
		option = self.shared_options.get(option_name)
		if option is None:
			return False

		value = option_value.rsplit(" (current)", 1)[0]
		if option.type is bool:
			value = option_value.startswith("True")

		try:
			option.type(value)
		except:
			return False

		option.value_from_string(value) # may be bool
		self.shared_options.set(option.name, option.value)
		return True
