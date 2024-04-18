import disnake

class OptionsController(disnake.View):
	def __init__(self, interaction, timeout=180.0, author=None):
		super().__init__(timeout=timeout)

		self.interaction = interaction
		self.author = author

		self.options_select_view = disnake.ui.StringSelect(min_values = 1, max_values = 25)
		self.options_select_view.add_option(label="Automatically clear queue after playing all (except loop)", value="auto_queue_clear", default=False)

		self.add_item(self.options_select_view)
	async def on_timeout(self):
		self.clear_items()
		await self.interaction.edit_original_response("Timed out", view=None)
	async def interaction_check(self, interaction):
		if self.author is not None:
			return self.author == interaction.author

	async def send_options(self):
		self.interaction.edit_original_response(view=self)