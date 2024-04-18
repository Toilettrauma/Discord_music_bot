from datetime import datetime
from typing import Union
from disnake import Interaction

class Logger:
	log_file = open("log.txt", "a", encoding="utf-16")
	@staticmethod
	def printline(event, info, user_or_inter : Union[str, Interaction] = "unknown"):
		if not isinstance(user_or_inter, str): # todo "not" change
			user_or_inter = user_or_inter.author.name
		time_string = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
		# Logger.log_file.write(b"[%s] (%s) %s : %s\n" % tuple(map(lambda s: s.encode("utf-16"), [time_string, user_or_inter, event, info])))
		# Logger.log_file.write("[%s] (%s) %s : %s\n" % (time_string, user_or_inter, event, info))
		Logger.log_file.write(f"[{time_string}] ({user_or_inter}) {event} : {info}\n")
		Logger.log_file.flush()