#!/usr/bin/env python

import re

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
		self.language = ""
		self.name = ""
		self.file_name = "" #Where the track is extracted to.

		#Video properties.
		self.pixel_width = 0
		self.pixel_height = 0
		self.display_width = 0
		self.display_height = 0
		self.interlaced = False
		self.interlace_field_order = "tff"
		self.pixel_aspect_ratio = "1:1"

		#Audio properties.
		self.frequency = 0
		self.channels = 0
		self.bit_depth = 0

	def from_mkv(self, mkv_track):
		print("---- Parsing track:")
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
			elif line.startswith("Track UID: "):
				line = line[len("Track UID: "):]
				try:
					self.uid = int(line)
					print("  UID:", self.uid)
				except ValueError: #Not an integer.
					pass
			elif line.startswith("Track type: "):
				line = line[len("Track type: "):]
				type_translation = {
					"video": "video",
					"audio": "audio",
					"subtitles": "subtitle"
				}
				if line in type_translation:
					self.type = type_translation[line]
					print("  Type:", self.type)
			elif line.startswith("Codec ID: "):
				line = line[len("Codec ID: "):]
				codec_translation = {
					"A_AAC": "aac",
					"A_FLAC": "flac",
					"A_TRUEHD": "truehd",
					"S_TEXT/ASS": "ass",
					"S_TEXT/UTF8": "srt",
					"V_MPEG4/ISO/AVC": "h264",
					"V_MPEGH/ISO/HEVC": "h265"
				}
				if line in codec_translation:
					self.codec = codec_translation[line]
					print("  Codec:", self.codec)
			elif line.startswith("Default duration: "):
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
			elif line.startswith("Language: "):
				line = line[len("Language: "):]
				language_translation = {
					"und": "",
					"chi": "zh_CN",
					"eng": "en_US",
					"fre": "fr_FR",
					"jpn": "ja_JP",
					"kor": "ko_KO",
					"spa": "es_ES",
					"tha": "th_TH"
				}
				if line in language_translation:
					self.language = language_translation[line]
					print("  Language:", self.language)
			elif line.startswith("Name: "):
				line = line[len("Name: "):]
				self.name = line
				print("  Name:", self.name)
			elif line.startswith("Pixel width: "):
				line = line[len("Pixel width: "):]
				try:
					self.pixel_width = int(line)
					print("  Pixel width:", self.pixel_width)
				except ValueError: #Not an integer.
					pass
			elif line.startswith("Pixel height: "):
				line = line[len("Pixel height: "):]
				try:
					self.pixel_height = int(line)
					print("  Pixel height:", self.pixel_height)
				except ValueError: #Not an integer.
					pass
			elif line.startswith("Display width: "):
				line = line[len("Display width: "):]
				try:
					self.display_width = int(line)
					print("  Display width:", self.display_width)
				except ValueError: #Not an integer.
					pass
			elif line.startswith("Display height: "):
				line = line[len("Display height: "):]
				try:
					self.display_height = int(line)
					print("  Display height:", self.display_height)
				except ValueError: #Not an integer.
					pass
			elif line.startswith("Sampling frequency: "):
				line = line[len("Sampling frequency: "):]
				try:
					self.frequency = int(line)
					print("  Frequency:", self.frequency)
				except ValueError: #Not an integer.
					pass
			elif line.startswith("Channels: "):
				line = line[len("Channels: "):]
				try:
					self.channels = int(line)
					print("  Channels:", self.channels)
				except ValueError: #Not an integer.
					pass
			elif line.startswith("Bit depth: "):
				line = line[len("Bit depth: "):]
				try:
					self.bit_depth = int(line)
					print("  Bit depth:", self.bit_depth)
				except ValueError: #Not an integer.
					pass

	def from_ffmpeg(self, track_nr, track_type, track_codec, interlaced=False, interlace_field_order="tff", pixel_aspect_ratio=1.0):
		self.track_nr = int(track_nr)

		type_translation = {
			"Video": "video",
			"Audio": "audio",
		}
		self.type = type_translation.get(track_type, "unknown")
		if self.type == "video":
			self.interlaced = interlaced
			self.interlace_field_order = interlace_field_order
			#Convert pixel aspect ratio from float to ratio.
			ratio = "1:1"
			for divisor in range(1, 1000):
				rounded = round(pixel_aspect_ratio * divisor)
				reconstructed = rounded / divisor
				difference = abs(reconstructed - pixel_aspect_ratio)
				if difference < 0.0005:
					ratio = "{rounded}:{divisor}".format(rounded=rounded, divisor=divisor)
					print("Aspect ratio", pixel_aspect_ratio, "converted into", ratio)
					break
			self.pixel_aspect_ratio = ratio

		codec_parts = track_codec.split(", ")
		codec_translation = {
			"ac3": "ac3",
			"dts": "dts",
			"pcm_bluray": "pcm_bluray",
			"h264": "h264",
			"mpeg2video": "mpg",
			"vc1": "vc1",
			"hdmv_pgs_subtitle": "pgs"
		}
		self.codec = codec_translation.get(codec_parts[0].strip(), "unknown")
		if self.codec in ["ac3", "flac", "dts", "pcm_bluray"]:
			if len(codec_parts) >= 2:
				frequency_str = codec_parts[1]
				if frequency_str.endswith(" Hz"):
					self.frequency = int(codec_parts[1][:-3])  # Remove " Hz"
			if len(codec_parts) >= 3:
				self.channels = 2 if codec_parts[2] == "stereo" else (1 if codec_parts[2] == "mono" else 0)
		elif self.codec in ["mpg", "h264", "vc1"]:
			fps_match = re.findall(r"[\.\d]+ fps", track_codec)
			if fps_match:
				self.fps = float(fps_match[0][:-4])  # Remove " fps"
				if self.interlaced:
					self.fps *= 2
			size_match = re.findall(r"\d+x\d+", track_codec)
			if size_match:
				size_parts = size_match[0].split("x")
				self.display_width = int(size_parts[0])
				self.display_height = int(size_parts[1])
