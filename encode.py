#!/usr/bin/env python

import argparse #To parse command line arguments.
import errno #To recognise OS errors.
import os #To delete files as clean-up.
import os.path #To parse file names (used for file type detection).
import shutil #To move files.
import subprocess #To call the encoders and muxers.
import uuid #To rename files to something that doesn't exist yet.

import attachment #To demux attachments.
import track #To demux tracks.

parser = argparse.ArgumentParser(description="Re-encode videos.")
parser.add_argument("input_filename", metavar="input", type=str, help="The input file name to encode.")
parser.add_argument("output_filename", metavar="output", type=str, help="The output file name to write to.")
parser.add_argument("--preset", dest="preset", type=str, help="Preset for encoding. Must be one of: 'hdanime', 'uhd'")
args = parser.parse_args()
input_filename = args.input_filename
output_filename = args.output_filename
preset = args.preset
if not preset:
	preset = input_filename.split("/")[0]
if preset == "output":
	exit() #This file is in the output folder. Ignore it.

#Ensure that the path for the output filename exists.
try:
	os.makedirs(os.path.dirname(output_filename))
except OSError as e:
	if e.errno != errno.EEXIST:
		print("Could not make output directory for file", output_filename, ":", e)
		exit()
except Exception as e:
	print("Could really not make output directory for file", output_filename, ":", e)
	exit()

print("===============AUTOENCODE===============")
print("==== INPUT:", input_filename)
print("==== OUTPUT:", output_filename)
print("==== PRESET:", preset)

guid = uuid.uuid4().hex #A new file name that is almost guaranteed to not exist yet.
extension = os.path.splitext(input_filename)[1]

def clean(files):
	"""Cleans up the changes we made after everything is done."""
	for file in files:
		try:
			os.remove(file)
		except Exception as e:
			print(e)

def extract_mkv(in_mkv):
	"""Extracts an MKV file into its components."""
	#Find all tracks and attachments in the MKV file.
	mkvinfo_command = ["mkvinfo", in_mkv]
	print(mkvinfo_command)
	process = subprocess.Popen(mkvinfo_command, stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0: #0 is success.
		raise Exception("Calling MKVInfo failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cerr.decode("utf-8")))
	mkvinfo = cout.decode("utf-8")
	tracks = []
	attachments = []
	for segment in mkvinfo.split("+ Segment, size")[1:]:
		for segment_item in segment.split("|+ ")[1:]:
			if segment_item.startswith("Segment tracks"):
				for track_metadata in segment_item.split("| + A track")[1:]:
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
	print("---- Extacting tracks...")
	extract_params = ["mkvextract", in_mkv, "tracks"] + track_params
	print(extract_params)
	process = subprocess.Popen(extract_params, stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0 and exit_code != 1: #0 is success. 1 is warnings.
		raise Exception("Calling MKVExtract on tracks failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cout.decode("utf-8")))
	if attachment_params: #Only extract attachments if there are attachments.
		print("Extracting attachments...")
		extract_params = ["mkvextract", in_mkv, "attachments"] + attachment_params
		print(extract_params)
		process = subprocess.Popen(extract_params, stdout=subprocess.PIPE)
		(cout, cerr) = process.communicate()
		exit_code = process.wait()
		if exit_code != 0 and exit_code != 1: #0 is success. 1 is warnings.
			raise Exception("Calling MKVExtract on attachments failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cout.decode("utf-8")))

	return tracks, attachments

def encode_flac(track_metadata):
	"""Encodes an audio file to the FLAC codec.
	This is sometimes used as an intermediary step when the opusenc codec doesn't support the audio file.
	Accepts any codec that FFmpeg supports (which is a lot)."""
	print("---- Encoding", track_metadata.file_name, "to FLAC...")
	new_file_name = track_metadata.file_name + ".flac"
	ffmpeg_command = ["ffmpeg", "-i", track_metadata.file_name, "-f", "flac", new_file_name]
	print(ffmpeg_command)
	process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0: #0 is success.
		raise Exception("Calling FFmpeg failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=str(cerr)))

	track_metadata.file_name = new_file_name
	track_metadata.codec = "flac"

def encode_opus(track_metadata):
	"""Encodes an audio file to the Opus codec.
	Accepted input codecs:
	- Wave
	- AIFF
	- FLAC
	- Ogg/FLAC
	- PCM"""
	print("---- Encoding", track_metadata.file_name, "to Opus...")
	new_file_name = track_metadata.file_name + ".opus"
	opusenc_command = ["opusenc", "--bitrate", "128", "--vbr", "--comp", "10", "--framesize", "60", track_metadata.file_name, new_file_name]
	print(opusenc_command)
	process = subprocess.Popen(opusenc_command, stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0: #0 is success.
		raise Exception("OpusEnc failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cerr))

	#Delete old file.
	if os.path.exists(track_metadata.file_name):
		os.remove(track_metadata.file_name)

	track_metadata.file_name = new_file_name
	track_metadata.codec = "opus"

def encode_h265(track_metadata):
	"""Encodes a video file to the H265 codec.
	Accepts any codec that FFmpeg supports (which is a lot)."""
	print("---- Encoding", track_metadata.file_name, "to H265...")
	new_file_name = track_metadata.file_name + ".265"
	stats_file = track_metadata.file_name + ".stats"
	vapoursynth_script = track_metadata.file_name + ".vpy"

	x265_presets = {
		"hdanime": {
			"preset": "8",
			"bitrate": "800",
			"deblock": "1:1"
		},
		"uhd": {
			"preset": "7",
			"bitrate": "3500",
			"deblock": "-2:0"
		}
	}

	#The encoding process produces some side effects that may need cleaning up.
	#Some are normally cleaned up but if the encoding is interrupted, be sure to delete them anyway.
	sideeffect_files = [
		track_metadata.file_name + ".stats.cutree.temp",
		track_metadata.file_name + ".stats.temp",
		track_metadata.file_name + ".ffindex",
		track_metadata.file_name + ".stats.cutree",
		track_metadata.file_name + ".stats"
	]

	#Generate VapourSynth script.
	script_source = preset + ".vpy"
	try:
		with open(os.path.join(os.path.split(__file__)[0], script_source)) as f:
			script = f.read()
		script = script.format(input_file=track_metadata.file_name)
		with open(vapoursynth_script, "w") as f:
			f.write(script)

		vspipe_command = ["vspipe", "--y4m", vapoursynth_script, "-"]
		x265_command = [
			"/home/ruben/encoding/x265/build2/x265",
			"-",
			"--y4m",
			"--fps", str(track_metadata.fps),
			"--preset", x265_presets[preset]["preset"],
			"--bitrate", x265_presets[preset]["bitrate"],
			"--deblock", x265_presets[preset]["deblock"],
			"-b", "12",
			"--psy-rd", "0.4",
			"--aq-strength", "0.5",
			"--stats", stats_file
		]
		x265_pass1 = ["--pass", "1", "-o", "/dev/null"]
		x265_pass2 = ["--pass", "2", "-o", new_file_name]
		pass1_command = " ".join(vspipe_command) + " | " + " ".join(x265_command + x265_pass1)
		print(pass1_command)
		process = subprocess.Popen(pass1_command, shell=True)
		(cout, cerr) = process.communicate()
		exit_code = process.wait()
		if exit_code != 0: #0 is success.
			raise Exception("First x265 pass failed with exit code {exit_code}.".format(exit_code=exit_code))
		pass2_command = " ".join(vspipe_command) + " | " + " ".join(x265_command + x265_pass2)
		print(pass2_command)
		process = subprocess.Popen(pass2_command, shell=True)
		(cout, cerr) = process.communicate()
		exit_code = process.wait()
		if exit_code != 0: #0 is success.
			raise Exception("Second x265 pass failed with exit code {exit_code}.".format(exit_code=exit_code))
	finally:
		#Delete old files and temporaries.
		for file_name in [track_metadata.file_name, stats_file, vapoursynth_script] + sideeffect_files:
			if os.path.exists(file_name):
				os.remove(file_name)

	track_metadata.file_name = new_file_name
	track_metadata.codec = "h265"

def mux_mkv(tracks, attachments):
	new_file_name = guid + "-out.mkv"

	mux_command = ["mkvmerge", "-o", new_file_name]
	title = os.path.splitext(os.path.split(input_filename)[1])[0]
	mux_command.append("--title")
	mux_command.append(title)

	for track_metadata in tracks:
		if track_metadata.type == "video":
			pass
		elif track_metadata.type == "audio":
			pass
		elif track_metadata.type == "subtitle":
			mux_command.append("--compression")
			mux_command.append(str(track_metadata.track_nr) + ":zlib")
		else:
			raise Exception("Unknown track type '{track_type}'".format(track_type = track_metadata.type))

		mux_command.append("--language")
		language_translation = { #Translate language codes to ISO639-2 format for MKVMerge.
			"": "und",
			"en_GB": "eng",
			"en_US": "eng",
			"es_ES": "spa",
			"fr_FR": "fra",
			"ja_JP": "jpn",
			"ko_KO": "kor",
			"nl_NL": "dut",
			"th_TH": "tha",
			"zh_CN": "zho",
			"zh_TW": "zho"
		}
		mux_command.append(str(track_metadata.track_nr) + ":" + language_translation[track_metadata.language]) #Gives KeyError if languages translation is incomplete.
		mux_command.append(track_metadata.file_name)

	for attachment_metadata in attachments:
		mux_command.append("--attachment-mime-type")
		mux_command.append(attachment_metadata.mime)
		mux_command.append("--attach-file")
		mux_command.append(attachment_metadata.file_name)

	print("---- Muxing...")
	print(mux_command)
	process = subprocess.Popen(mux_command, stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0 and exit_code != 1: #0 is success. 1 is warnings.
		raise Exception("Calling MKVMerge failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cout.decode("utf-8")))
	if exit_code == 1:
		print("MKVMerge warning:", cout.decode("utf-8"))

dirty_files = []
try:
	if preset == "uhd" or preset == "hdanime":
		if extension == ".mkv":
			#Demuxing.
			tracks, attachments = extract_mkv(input_filename) #Encoding.
			dirty_files = [track.file_name for track in tracks] + [attachment.file_name for attachment in attachments]
			for track_metadata in tracks:
				if track_metadata.codec == "flac":
					encode_opus(track_metadata)
				elif track_metadata.codec == "aac" or track_metadata.codec == "truehd":
					original_filename = track_metadata.file_name
					encode_flac(track_metadata)
					if os.path.exists(original_filename):
						os.remove(original_filename)
					encode_opus(track_metadata)
				elif track_metadata.codec == "h264" or track_metadata.codec == "h265":
					encode_h265(track_metadata)
				else:
					print("Unknown codec:", track_metadata.codec) #Muxing.
			mux_mkv(tracks, attachments)
			shutil.move(guid + "-out.mkv", output_filename)
		else:
			raise Exception("Unknown file extension for UHD or HDAnime: {extension}".format(extension=extension))
	elif preset == "opus":
		if extension in [".flac", ".wav", ".aiff"]:
			trk = track.Track()
			trk.file_name = input_filename
			dirty_files = [input_filename]
			encode_opus(trk)
			shutil.move(trk.file_name, os.path.splitext(output_filename)[0] + ".opus")
		elif extension in [".mp3", ".aax", ".aa", ".acm", ".bfstm", ".brstm", ".caf", ".genh", ".mp2", ".mp4", ".msf", ".midi", ".ogg", ".ac3", ".dts", ".pcm", ".rm", ".rl2", ".ta", ".wma", ".aac", ".alac", ".mp1", ".opus", ".vmd", ".tta"]:
			trk = track.Track()
			trk.file_name = input_filename
			encode_flac(trk)
			dirty_files = [input_filename, trk.file_name]
			encode_opus(trk)
			shutil.move(trk.file_name, os.path.splitext(output_filename)[0] + ".opus")
		else:
			raise Exception("Unknown file extension for Opus: {extension}".format(extension=extension))
	else:
		raise Exception("Unknown preset: {preset}".format(preset=preset))
finally:
	clean(dirty_files) #Clean up after any mistakes.
