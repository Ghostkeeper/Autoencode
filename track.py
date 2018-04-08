#!/usr/bin/env python

class Track:
	"""
	Represents one track in a media container.
	"""

	def __init__(self):
		self.track_nr = -1
		self.uid = -1
		self.type = ""
		self.codec = ""
		self.duration = 0.0
		self.language = "und"
		self.name = ""

		#Video properties.
		self.pixel_width = 0
		self.pixel_height = 0
		self.display_width = 0
		self.display_height = 0

		#Audio properties.
		self.frequency = 0
		self.channels = 0
		self.bit_depth = 0

	def from_mkv(self, mkv_track):
		print("Parsing track:")
		for line in mkv_track.split("\n"):
			if line.startswith("|"):
				line = line[1:]
			line = line.strip()
			if line.startswith("+"):
				line = line[1:]
			line = line.strip()

			if line.startswith("Track number: ") and "mkvextract:" in line:
				line = line[line.find("mkvextract: ") + len("mkvextract: "):]
				if ")" in line:
					line = line[:line.find(")")]
					try:
						self.track_nr = int(line)
						print("  Track Nr:", self.track_nr)
					except TypeError: #Not properly formatted for int().
						pass
			if line.startswith("Track UID: "):
				line = line[len("Track UID: "):]
				try:
					self.uid = int(line)
					print("  UID:", self.uid)
				except TypeError: #Not an integer.
					pass
