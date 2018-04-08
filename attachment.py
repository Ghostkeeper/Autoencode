#!/usr/bin/env python

class Attachment:
	"""
	Represents the metadata of an attachment in a container file.
	"""

	def __init__(self):
		self.internal_name = ""
		self.mime = ""
		self.uid = -1

	def from_mkv(self, mkv_attachment):
		print("Parsing attachment:")
		for line in mkv_attachment.split("\n"):
			if line.startswith("|"):
				line = line[1:]
			line = line.strip()
			if line.startswith("+"):
				line = line[1:]
			line = line.strip()

			if line.startswith("File name: "):
				line = line[len("File name: "):]
				self.internal_name = line
				print("  Internal name:", self.internal_name)
			elif line.startswith("MIME type: "):
				line = line[len("MIME type: "):]
				self.mime = line
				print("  MIME type:", self.mime)
