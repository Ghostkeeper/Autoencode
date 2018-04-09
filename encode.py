#!/usr/bin/env python

import argparse #To parse command line arguments.
import os #To delete files as clean-up.
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

def clean(tracks = [], attachments = []):
	"""Cleans up the changes we made after everything is done."""
	try:
		shutil.move(guid + extension, input_filename)
	except Exception as e:
		print(e) #Can't recover, but continue with the rest of the clean-up.
	for track_metadata in tracks:
		try:
			os.remove(track_metadata.file_name)
		except Exception as e:
			print(e)
	for attachment_metadata in attachments:
		try:
			os.remove(attachment_metadata.file_name)
		except Exception as e:
			print(e)

def extract_mkv(in_mkv):
	#Find all tracks and attachments in the MKV file.
	process = subprocess.Popen(["mkvinfo", in_mkv], stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0: #0 is success.
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
	attachment_params = []
	for attachment_metadata in attachments:
		attachment_params.append(str(attachment_metadata.aid) + ":" + attachment_metadata.file_name)

	#Extract all tracks and attachments.
	print("Extacting tracks...")
	process = subprocess.Popen(["mkvextract", in_mkv, "tracks"] + track_params, stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0 and exit_code != 1: #0 is success. 1 is warnings.
		raise Exception("Calling MKVExtract on tracks failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cout.decode("utf-8")))
	print("Extracting attachments...")
	process = subprocess.Popen(["mkvextract", in_mkv, "attachments"] + attachment_params, stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0 and exit_code != 1: #0 is success. 1 is warnings.
		raise Exception("Calling MKVExtract on attachments failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cout.decode("utf-8")))

	return tracks, attachments

def encode_flac(track_metadata):
	new_file_name = track_metadata.file_name + ".opus"
	process = subprocess.Popen(["opusenc", "--bitrate", "96", "--vbr", "--comp", "10", "--framesize", "60", track_metadata.file_name, new_file_name], stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0: #0 is success.
		raise Exception("OpusEnc failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cerr))

	#Delete old file.
	os.remove(track_metadata.file_name)

	track_metadata.file_name = new_file_name
	track_metadata.codec = "opus"

def encode_h264(track_metadata):
	new_file_name = track_metadata.file_name + ".265"
	stats_file = track_metadata.file_name + ".stats"
	process = subprocess.Popen(["/home/ruben/encoding/x265/build/x265", "--preset", "9", "--bitrate", "1000", "--deblock", "1:1", "-b", "12", "--psy-rd", "0.4", "--aq-strength", "0.5", "--pass", "1", "--stats", stats_file, "-o", "/dev/null", track_metadata.file_name], stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0: #0 is success.
		raise Exception("x265 failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cerr))

	#Delete old file.
	#os.remove(track_metadata.file_name)

	#track_metadata.file_name = new_file_name
	#track_metadata.codec = "h265"

try:
	#Demuxing.
	tracks = []
	attachments = []
	if extension == ".mkv":
		tracks, attachments = extract_mkv(guid + ".mkv")
	else:
		raise Exception("Unknown file extension: {extension}".format(extension=extension))

	#Encoding.
	for track_metadata in tracks:
		if track_metadata.codec == "flac":
			encode_flac(track_metadata)
		elif track_metadata.codec == "h264":
			encode_h264(track_metadata)
		else:
			print("Unknown codec:", track_metadata.codec)
finally:
	clean(tracks, attachments) #Clean up after any mistakes.
