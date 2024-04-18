import disnake

class VoteController:
	def __init__(self, interaction, user, vote_name):
		self.interaction = interaction
		self.vote_name = vote_name
		self.user = user
		self.f1s = 0
		self.f2s = 0

		self.content = "Голосование: %s %s?" % (user, vote_name)
		self.view = disnake.ui.View(timeout=10.0)
		self.view.on_timeout = self.timeout
		self.f1_button = disnake.ui.Button(style=disnake.ButtonStyle.success, label="F1 0")
		self.f1_button.callback = self.f1_clicked
		self.f2_button = disnake.ui.Button(style=disnake.ButtonStyle.danger, label="F2 0")
		self.f2_button.callback = self.f2_clicked
		self.view.add_item(self.f1_button)
		self.view.add_item(self.f2_button)

	async def send(self):
		await self.interaction.send(self.content, view=self.view)
	async def f1_clicked(self, interaction):
		self.f1s += 1
		self.f1_button.label = "F1 %i" % self.f1s
		await interaction.response.defer(with_message=False)

		await self.interaction.edit_original_message(view=self.view)
	async def f2_clicked(self, interaction):
		self.f2s += 1
		self.f2_button.label = "F2 %i" % self.f2s
		await interaction.response.defer(with_message=False)

		await self.interaction.edit_original_message(view=self.view)
	async def timeout(self):
		message = await self.interaction.original_message()
		if self.f1s >= self.f2s:
			await message.reply("Голосование окончено: %s %s" % (self.user, self.vote_name))
		else:
			await message.reply("Голосование окончено: %s не %s" % (self.user, self.vote_name))

		self.f1_button.disabled = True
		self.f2_button.disabled = True

		await self.interaction.edit_original_message(view=self.view)