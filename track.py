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
		self.fps = 0.0
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
					except ValueError: #Not properly formatted for int().
						pass
			if line.startswith("Track UID: "):
				line = line[len("Track UID: "):]
				try:
					self.uid = int(line)
					print("  UID:", self.uid)
				except ValueError: #Not an integer.
					pass
			if line.startswith("Track type: "):
				line = line[len("Track type: "):]
				type_translation = {
					"video": "video",
					"audio": "audio",
					"subtitles": "subtitle"
				}
				if line in type_translation:
					self.type = type_translation[line]
					print("  Type:", self.type)
			if line.startswith("Codec ID: "):
				line = line[len("Codec ID: "):]
				codec_translation = {
					"A_FLAC": "flac",
					"S_TEXT/ASS": "ass",
					"V_MPEG4/ISO/AVC": "h264"
				}
				if line in codec_translation:
					self.codec = codec_translation[line]
					print("  Codec:", self.codec)
			if line.startswith("Default duration: "):
				line = line[len("Default duration: "):]
				line = line[:line.find(" ")]
				try:
					hours, minutes, seconds = line.split(":")
					hours = int(hours)
					minutes = int(minutes)
					seconds = float(seconds)
					frame_duration = hours * 3600 + minutes * 60 + seconds
					self.fps = 1.0 / frame_duration
					print("  FPS:", self.fps)
				except ValueError: #Too many or not enough values to unpack, or not ints/floats.
					pass
