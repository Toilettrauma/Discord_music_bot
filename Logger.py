from datetime import datetime
from typing import Union
import disnake

class Logger:
	log_file = open("log.txt", "a", encoding="utf-16")
	@staticmethod
	def printline(event, info, user_or_inter : Union[str, disnake.Interaction] = "unknown"):
		user = None
		if isinstance(user_or_inter, disnake.Interaction):
			user = user_or_inter.author.name
		elif isinstance(user_or_inter, str):
			user = user_or_inter
		else:
			print("[ERROR] Logger error")
			return
		time_string = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
		# Logger.log_file.write(b"[%s] (%s) %s : %s\n" % tuple(map(lambda s: s.encode("utf-16"), [time_string, user_or_inter, event, info])))
		# Logger.log_file.write("[%s] (%s) %s : %s\n" % (time_string, user_or_inter, event, info))
		Logger.log_file.write(f"[{time_string}] ({user}) {event} : {info}\n")
		Logger.log_file.flush()