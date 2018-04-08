#!/usr/bin/env python

import argparse #To parse command line arguments.
import os.path #To parse file names (used for file type detection).
import shutil #To move files.
import subprocess #To call the encoders and muxers.
import uuid #To rename files to something that doesn't exist yet.

import attachment #To demux attachments.
import track #To demux tracks.

parser = argparse.ArgumentParser(description="Re-encode videos.")
parser.add_argument("input_filename", metavar="input", type=str, help="The input file name to encode.")
parser.add_argument("--preset", dest="preset", type=str, help="Preset for encoding. Must be one of: 'sd', 'hd', 'animated'")
args = parser.parse_args()
input_filename = args.input_filename
preset = args.preset

guid = uuid.uuid4().hex #A new file name that is almost guaranteed to not exist yet.
extension = os.path.splitext(input_filename)[1]
shutil.move(input_filename, guid + extension)

def clean():
	"""Cleans up the changes we made after everything is done."""
	try:
		shutil.move(guid + extension, input_filename)
	except Exception as e:
		print(e)
		pass #Can't recover, but continue with the rest of the clean-up.

def extract_mkv(in_mkv):
	#Find all tracks and attachments in the MKV file.
	process = subprocess.Popen(["mkvinfo", in_mkv], stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0:
		raise Exception("Calling MKVInfo failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cerr.decode("utf-8")))
	mkvinfo = cout.decode("utf-8")
	tracks = []
	attachments = []
	for segment in mkvinfo.split("+ Segment:")[1:]:
		for segment_item in segment.split("|+ ")[1:]:
			if segment_item.startswith("Tracks"):
				for track_metadata in segment_item.split("| + Track")[1:]:
					new_track = track.Track()
					new_track.from_mkv(track_metadata)
					new_track.file_name = guid + "-T" + str(new_track.track_nr)
					tracks.append(new_track)
			if segment_item.startswith("Attachments"):
				for attachment_metadata in segment_item.split("| + Attached")[1:]:
					new_attachment = attachment.Attachment()
					new_attachment.from_mkv(attachment_metadata)
					attachments.append(new_attachment)
					new_attachment.aid = len(attachments)
					new_attachment.file_name = guid + "-A" + str(new_attachment.aid)

	#Generate the parameters to pass to mkvextract.
	track_params = []
	for track_metadata in tracks:
		track_params.append(str(track_metadata.track_nr) + ":" + track_metadata.file_name)
	track_params = " ".join(track_params)
	attachment_params = []
	for attachment_metadata in attachments:
		attachment_params.append(str(attachment_metadata.uid) + ":" + attachment_metadata.file_name)
	attachment_params = " ".join(attachment_params)

	return tracks, attachments

try:
	tracks = []
	attachments = []
	if extension == ".mkv":
		tracks, attachments = extract_mkv(guid + ".mkv")
	else:
		raise Exception("Unknown file extension: {extension}".format(extension=extension))
finally:
	clean() #Clean up after any mistakes.
