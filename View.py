import disnake

class CustomModal(disnake.ui.Modal):
	def __init__(self, callback, *args, **kvargs):
		super().__init__(*args, **kvargs)
		self._callback = callback
	async def callback(self, interaction):
		await self._callback(interaction)