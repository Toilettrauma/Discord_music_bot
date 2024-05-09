import subprocess
import os
import re

if __name__ == "__main__":
	package_info = subprocess.check_output("pip show youtube_dl --no-color").decode("utf-8")
	if package_info.startswith("WARNING"):
		print("ERROR: youtube_dl not found")

	ydl_location = None
	for info_line in package_info.split("\r\n"):
		if info_line.startswith("Location"):
			ydl_location = info_line.split("Location: ")[1]
			break
	else:
		print("ERROR: Location line not found in 'pip show'")

	ydl_path = os.path.join(ydl_location, "youtube_dl\\extractor")
	uploader_id_patched = False
	with open(os.path.join(ydl_path, "youtube.py"), encoding="utf-8") as in_fp, \
		 open(os.path.join(ydl_path, "youtube_patched.py"), "w", encoding="utf-8") as out_fp:
		for line in in_fp:
			if "'uploader_id': self._search_regex(r'/(?:channel|user)" in line:
				print("PATCH: uploader_id")
				uploader_id_patched = True
				line = line.replace("(?:channel|user)/", "(?:channel/|user/|@)")
			out_fp.write(line)

	if not uploader_id_patched:
		print("ERROR: failed to patchfind")
		os.remove(os.path.join(ydl_path, "youtube_patched.py"))

	os.remove(os.path.join(ydl_path, "youtube.py"))
	os.rename(os.path.join(ydl_path, "youtube_patched.py"), os.path.join(ydl_path, "youtube.py"))

	print("SUCCESS: patched")
	input()