#!/usr/bin/env python

import argparse #To parse command line arguments.
import errno #To recognise OS errors.
import glob #To find concatenated files.
import os #To delete files as clean-up.
import os.path #To parse file names (used for file type detection).
import re #To parse the stream info output.
import shutil #To move files.
import subprocess #To call the encoders and muxers.
import uuid #To rename files to something that doesn't exist yet.

import attachment #To demux attachments.
import track #To demux tracks.

def process(input_filename, output_filename, preset):
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
	if not os.path.exists(input_filename):
		print(f"==== INPUT {input_filename} no longer exists.")
		return

	print("===============AUTOENCODE===============")
	print("==== INPUT:", input_filename)
	print("==== OUTPUT:", output_filename)
	print("==== PRESET:", preset)

	guid = uuid.uuid4().hex #A new file name that is almost guaranteed to not exist yet.
	extension = os.path.splitext(input_filename)[1]
	extension = extension.lower()

	dirty_files = []
	try:
		if preset == "uhd" or preset == "hdanime":
			if extension == ".mkv":
				#Demuxing.
				tracks, attachments = extract_mkv(input_filename, guid) #Encoding.
				dirty_files = [trk.file_name for trk in tracks] + [attachment.file_name for attachment in attachments]
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
						encode_h265(track_metadata, preset)
					else:
						print("Unknown codec:", track_metadata.codec)
				#Muxing.
				mux_mkv(tracks, attachments, guid, input_filename)
				shutil.move(guid + "-out.mkv", output_filename)
			else:
				raise Exception("Unknown file extension for UHD or HDAnime: {extension}".format(extension=extension))
		elif preset == "dvd":
			if extension == ".vob":
				input_ffmpegname = None
				
				all_paths = [input_filename]
				#Only process the zeroth file of DVD files.
				match = re.search(r"VTS_\d+_(\d+).VOB$", input_filename)
				if os.path.exists(os.path.join(os.path.dirname(input_filename), "VIDEO_TS.IFO")):
					#If there is a VIDEO_TS.IFO file, skip all .VOB files and process that one instead as titles.
					print("Skipping {input_filename} because there is an .IFO file with titles.".format(input_filename=input_filename))
				elif match:
					if match.group(1) != "0" and os.path.exists(input_filename[:-len(match.group(1)) - 4] + "_0.VOB"):
						print("Skipping {input_filename} because it's not the main file of the VOB chain.".format(input_filename=input_filename))
					else:
						if input_filename.endswith("_0.VOB"):
							#Concatenate all of the components of this one stream together.
							find_path = input_filename[:-len(match.group(1)) - 4] + "*.VOB" #Replace the 0 with a *.
							def humansort(text):
								return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", text)]
							all_paths = sorted(glob.glob(find_path), key=humansort)
							if len(all_paths) > 1:
								input_ffmpegname = "concat:" + "|".join(all_paths)
							else:
								input_ffmpegname = all_paths[0]
						else:
							input_ffmpegname = input_filename
				else:
					if os.path.basename(input_filename).startswith("VTS_") and input_filename.endswith("_0.VOB"):
						#Concatenate all of the components of this one stream together.
						find_path = input_filename[:-5] + "*.VOB" #Replace the 0 with a *.
						all_paths = sorted(glob.glob(find_path))
						if len(all_paths) > 1:
							input_ffmpegname = "concat:" + "|".join(all_paths)
						else:
							input_ffmpegname = all_paths[0]
					else:
						input_ffmpegname = input_filename

				if input_ffmpegname is not None:
					#Demuxing.
					tracks = extract_vob(input_ffmpegname, guid)
					dirty_files = [trk.file_name for trk in tracks]
					for track_metadata in tracks:
						if track_metadata.codec == "ac3":
							original_filename = track_metadata.file_name
							encode_flac(track_metadata)
							if os.path.exists(original_filename):
								os.remove(original_filename)
							encode_opus(track_metadata)
							dirty_files.append(track_metadata.file_name)
						elif track_metadata.codec == "mpg":
							encode_h265(track_metadata, preset)
							dirty_files.append(track_metadata.file_name)
						elif track_metadata.codec == "sub":
							pass #Leave image-encoded subs as-is for now.
						else:
							print("Unknown codec:", track_metadata.codec)
					#Muxing.
					mux_mkv(tracks, [], guid, input_filename)
					shutil.move(guid + "-out.mkv", os.path.splitext(output_filename)[0] + ".mkv")
					dirty_files += all_paths
			elif extension == ".ifo":
				if os.path.basename(input_filename) != "VIDEO_TS.IFO":
					print("Skipping {input_filename} because it's not the right IFO file.".format(input_filename=input_filename))
				else:
					split_dvd(os.path.dirname(input_filename))
					# After splitting the DVD, delete all original DVD files. Instead we'll process the split versions.
					dirty_files += list(glob.glob("VTS_*_*.VOB"))
					dirty_files += list(glob.glob("VTS_*_*.BUP"))
					dirty_files += list(glob.glob("VTS_*_*.IFO"))
					dirty_files += ["VIDEO_TS.IFO", "VIDEO_TS.BUP", "VIDEO_TS.VOB"]
			else:
				raise Exception("Unknown file extension for DVD: {extension}".format(extension=extension))
		elif preset == "strip_subs":
			if extension == ".mkv":
				ffmpeg("-i", input_filename, "-y", "-map", "0:v", "-map", "0:a", "-sn", "-c:v", "copy", "-c:a", "copy", output_filename)
				os.remove(input_filename)
			else:
				raise Exception("Unknown file extension for stripping subtitles: {extension}".format(extension=extension))
		elif preset == "jpg":
			if extension in [".jpg", ".jpeg"]:
				trk = track.Track()
				trk.file_name = input_filename
				dirty_files = [input_filename]
				encode_jpg(trk)
				shutil.move(trk.file_name, os.path.splitext(output_filename)[0] + ".jpg")
			elif extension in [".mkv", ".vob"]:
				frames = extract_video_frames(input_filename)
				dirty_files = [input_filename]
				output_directory = os.path.dirname(output_filename)
				for frame in frames:
					encode_jpg(frame)
					frame_output = os.path.join(output_directory, frame.file_name[:-4])
					shutil.move(frame.file_name, frame_output)
			else:
				raise Exception("Unknown file extension for JPG: {extension}".format(extension=extension))
		elif preset == "opus":
			if extension in [".flac", ".wav", ".aiff"]:
				trk = track.Track()
				trk.file_name = input_filename
				dirty_files = [input_filename]
				encode_opus(trk)
				shutil.move(trk.file_name, os.path.splitext(output_filename)[0] + ".opus")
			elif extension in [".mp3", ".aax", ".aa", ".acm", ".bfstm", ".brstm", ".caf", ".genh", ".mp2", ".mp4", ".msf", ".midi", ".ogg", ".ac3", ".dts", ".pcm", ".rm", ".rl2", ".ta", ".wma", ".aac", ".alac", ".mp1", ".opus", ".vmd", ".tta", ".m4a", ".wv"]:
				trk = track.Track()
				trk.file_name = input_filename
				encode_flac(trk)
				dirty_files = [input_filename, trk.file_name]
				encode_opus(trk)
				shutil.move(trk.file_name, os.path.splitext(output_filename)[0] + ".opus")
			else:
				raise Exception("Unknown file extension for Opus: {extension}".format(extension=extension))
		elif preset == "png":
			if extension in [".png", ".bmp", ".gif", ".pnm", ".tif", ".tiff"]:
				trk = track.Track()
				trk.file_name = input_filename
				dirty_files = [input_filename]
				encode_png(trk)
				shutil.move(trk.file_name, os.path.splitext(output_filename)[0] + ".png")
			else:
				raise Exception("Unknown file extension for PNG: {extension}".format(extension=extension))
		elif preset == "flac":
			if extension in [".flac", ".wav", ".aiff", ".mp3", ".aax", ".aa", ".acm", ".bfstm", ".brstm", ".caf", ".genh", ".mp2", ".mp4", ".msf", ".midi", ".ogg", ".ac3", ".dts", ".pcm", ".rm", ".rl2", ".ta", ".wma", ".aac", ".alac", ".mp1", ".opus", ".vmd", ".tta", ".m4a", ".wv"]:
				trk = track.Track()
				trk.file_name = input_filename
				dirty_files = [input_filename]
				encode_flac(trk)
				shutil.move(trk.file_name, os.path.splitext(output_filename)[0] + ".flac")
			else:
				raise Exception("Unknown file extension for FLAC: {extension}".format(extension=extension))
		else:
			raise Exception("Unknown preset: {preset}".format(preset=preset))
	finally:
		clean(dirty_files) #Clean up after any mistakes.

def clean(files):
	"""Cleans up the changes we made after everything is done."""
	for file in files:
		try:
			os.remove(file)
		except Exception as e:
			print(e)

def split_dvd(in_directory):
	if os.path.exists(os.path.join(in_directory, "title1.VOB")):
		raise Exception("Already extracted a DVD here. Will not override.")
	list_command = ["lsdvd", "-x", in_directory]
	print(list_command)
	process = subprocess.Popen(list_command, stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0:
		raise Exception("Calling lsdvd resulted in exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cout.decode("utf-8")))

	cout = cout.decode("utf-8")
	lines = cout.split("\n")
	for line_nr, line in enumerate(lines):
		if line.startswith("Title: "):
			title_pos = len("Title: ")
			cells_pos = len("Title: XX, Length: HH:MM:SS.XXX Chapters: XX, Cells: ")
			angles_pos = len("\tNumber of Angles: ")
			title_nr = str(int(line[title_pos:title_pos + 2]))
			num_cells = str(int(line[cells_pos:cells_pos + 2]))
			num_angles = int(lines[line_nr + 3][angles_pos:])

			for this_angle in range(num_angles):
				anglepart = ""
				if num_angles > 1:
					anglepart = "-" + str(this_angle + 1)
				extract_command = ["mplayer", "dvd://" + title_nr, "-dvd-device", in_directory, "-chapter", "0-" + num_cells, "-dvdangle", str(this_angle + 1), "-dumpstream", "-dumpfile", os.path.join(in_directory, "title" + title_nr + anglepart + ".VOB")]
				print(extract_command)
				process = subprocess.Popen(extract_command, stdout=subprocess.PIPE)
				(cout, cerr) = process.communicate()
				exit_code = process.wait()
				if exit_code != 0:
					raise Exception("Calling mplayer resulted in exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cout.decode("utf-8")))

def extract_mkv(in_mkv, guid):
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
	for segment in mkvinfo.split("+ Segment: size")[1:]:
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

def extract_vob(in_vob, guid):
	"""Extracts a VOB file into audio and video components."""
	if in_vob.startswith("concat:"):
		probe_vob = in_vob.split("|")[-1] #Can only take mediainfo from one file at a time. Pick the last one.
	else:
		probe_vob = in_vob

	#Detect interlacing.
	mediainfo_command = "mediainfo --Inform='Video;%ScanType%,%ScanOrder%,%PixelAspectRatio%,%Standard%' \"" + probe_vob + "\""
	print(mediainfo_command)
	process = subprocess.Popen(mediainfo_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0:
		raise Exception("Calling Mediainfo on {probe_vob} failed with exit code {exit_code}.".format(probe_vob=probe_vob, exit_code=exit_code))
	mediainfo_parts = cout.decode("utf-8").split(",")
	is_interlaced = mediainfo_parts[0] == "Interlaced"
	field_order = mediainfo_parts[1].lower().strip()
	print("Interlace detection:", is_interlaced, field_order, "(", mediainfo_parts, ")")
	pixel_aspect_ratio = float(mediainfo_parts[2])
	standard = mediainfo_parts[3]
	print("Standard:", standard)
	if standard.strip() == "PAL":
		pixel_aspect_ratio = 1.42222  # Sometimes the PAR is wrong for some reason. Standard is more reliable.
	print("Pixel aspect ratio:", pixel_aspect_ratio)

	ffmpeg_command = ["ffmpeg", "-probesize", "10M", "-analyzeduration", "50000000", "-i", in_vob]
	print(ffmpeg_command)
	process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	process.wait() #Ignore the exit code. It always fails.
	vobinfo = cerr.decode("utf-8")
	vobinfo = re.sub(r"\(.*?\)", "", vobinfo)  # Remove parts between brackets. It messes up parsing.
	tracks = []
	for match in re.finditer(r"  Stream #0:(\d+)\[0x[0-9a-f]+\]: (\w+): ([^\n]+)", vobinfo):
		track_nr = match.group(1)
		track_type = match.group(2)
		track_codec = match.group(3)
		new_track = track.Track()
		new_track.from_vob(track_nr, track_type, track_codec, is_interlaced, field_order, pixel_aspect_ratio)
		new_track.file_name = guid + "-T" + str(new_track.track_nr) + "." + new_track.codec
		if new_track.type != "unknown":
			tracks.append(new_track)

	#Generate the parameters to pass to ffmpeg.
	track_params = ["-probesize", "10M", "-analyzeduration", "50000000", "-i", in_vob]
	for track_metadata in tracks:
		track_params.append("-map")
		track_params.append("0:" + str(track_metadata.track_nr))
		track_params.append("-c")
		track_params.append("copy")
		track_params.append(track_metadata.file_name)

	#Extract all tracks.
	print("---- Extracting tracks...")
	ffmpeg(*track_params)

	return tracks

def extract_video_frames(in_vid):
	"""
	Extract a video file into individual frames.

	Any video type supported by both MediaInfo and FFMPEG is supported by this function.
	However multi-part VOB files could be problematic.

	Audio is discarded.
	:return: A list of tracks, one for each frame, to encode further.
	"""
	if in_vid.startswith("concat:"):
		probe_vob = in_vid.split("|")[-1] #Can only take mediainfo from one file at a time. Pick the last one.
	else:
		probe_vob = in_vid

	#Detect aspect ratio.
	mediainfo_command = "mediainfo --Inform='Video;%Width%,%Height%,%PixelAspectRatio%,%Standard%' \"" + probe_vob + "\""
	print(mediainfo_command)
	process = subprocess.Popen(mediainfo_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0:
		raise Exception("Calling Mediainfo on {probe_vob} failed with exit code {exit_code}.".format(probe_vob=probe_vob, exit_code=exit_code))
	mediainfo_parts = cout.decode("utf-8").split(",")
	width = int(mediainfo_parts[0])
	height = int(mediainfo_parts[1])
	pixel_aspect_ratio = float(mediainfo_parts[2])
	standard = mediainfo_parts[3]
	print("Standard:", standard)
	if standard.strip() == "PAL":
		pixel_aspect_ratio = 1.42222  # Sometimes the PAR is wrong for some reason. Standard is more reliable.
	print("Pixel aspect ratio:", pixel_aspect_ratio)

	new_file_name = probe_vob + "-%05d.png"
	scale_filter = "scale={width}x{height}".format(width=str(int(width*pixel_aspect_ratio)), height=str(height))
	ffmpeg_command = ["ffmpeg", "-i", in_vid, "-vsync", "0", "-vf", scale_filter, new_file_name]
	print(ffmpeg_command)
	process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0:
		raise Exception("Calling FFMPEG on VOB failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cout.decode("utf-8")))

	images = glob.glob(probe_vob + "-*.png")
	tracks = []
	for image in images:
		#Crop each image.
		output_file = image[:-4] + ".jpg"
		imagemagick_command = ["convert", image, "-bordercolor", "black", "-border", "1x1", "-fuzz", "10%", "-trim", output_file]
		print(imagemagick_command)
		process = subprocess.Popen(imagemagick_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		(cout, cerr) = process.communicate()
		exit_code = process.wait()
		if exit_code != 0:
			raise Exception("Calling ImageMagick on JPG failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cout.decode("utf-8")))

		#Create a track.
		new_track = track.Track()
		new_track.codec = "jpg"
		new_track.file_name = image
		tracks.append(new_track)

	return tracks

def encode_flac(track_metadata):
	"""
	Encodes an audio track to the FLAC codec.

	The aim of this encode is to encode losslessly, so all of the original file
	parameters are kept (frequency, bit depth). Within those parameters, it
	tries to encode to the smallest file size.

	Accepts any codec that FFmpeg supports (which is a lot).
	"""
	print("---- Encoding", track_metadata.file_name, "to FLAC...")
	new_file_name = track_metadata.file_name + ".flac"
	ffmpeg("-i", track_metadata.file_name, "-c:a", "flac", "-compression_level", "12", "-lpc_passes", "8", "-lpc_type", "3", "-threads", "12", new_file_name)

	track_metadata.file_name = new_file_name
	track_metadata.codec = "flac"

def encode_jpg(track_metadata):
	"""
	Optimises a JPG image.

	This encoding only accepts JPG files as input. It will always encode
	losslessly (save for metadata) to optimise compression.
	"""
	print("---- Encoding", track_metadata.file_name, "to JPG...")
	new_file_name = track_metadata.file_name + ".jpg"
	shutil.copy(track_metadata.file_name, new_file_name)  #Work only on a copy.
	ect_command = ["/home/ruben/Projects/Clones/Efficient-Compression-Tool/build/ect", "-9", "-strip", "--mt-deflate", new_file_name]
	print(ect_command)
	process = subprocess.Popen(ect_command, stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if(exit_code != 0): #0 is success.
		raise Exception("ECT failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cerr))

	#Delete old file.
	if os.path.exists(track_metadata.file_name):
		os.remove(track_metadata.file_name)

	track_metadata.file_name = new_file_name
	track_metadata.codec = "jpg"

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

def encode_png(track_metadata):
	"""
	Encodes a picture in PNG.
	Accepted input codecs:
	- PNG
	- BMP
	- GIF
	- PNM
	- TIFF
	"""
	print("---- Encoding", track_metadata.file_name, "to PNG...")

	# First step: OptiPNG.
	new_file_name = track_metadata.file_name + ".png"
	optipng_command = ["optipng", "-o7", "-strip", "all", "-snip", "-out", new_file_name, track_metadata.file_name]
	print(optipng_command)
	process = subprocess.Popen(optipng_command, stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0: #0 is success.
		raise Exception("OptiPNG failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cerr))

	ect_command = ["/home/ruben/encoding/Efficient-Compression-Tool/build/ect", "-9", "-strip", "--allfilters-b", "--mt-deflate", new_file_name]
	print(ect_command)
	process = subprocess.Popen(ect_command, stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0: #0 is success.
		raise Exception("ECT failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cerr))

	#Delete old file.
	if os.path.exists(track_metadata.file_name):
		os.remove(track_metadata.file_name)

	track_metadata.file_name = new_file_name
	track_metadata.codec = "png"

def encode_h265(track_metadata, preset):
	"""Encodes a video file to the H265 codec.
	Accepts any codec that FFmpeg supports (which is a lot)."""
	print("---- Encoding", track_metadata.file_name, "to H265...")
	new_file_name = track_metadata.file_name + ".265"
	stats_file = track_metadata.file_name + ".stats"
	vapoursynth_script = track_metadata.file_name + ".vpy"

	#Get the number of frames, to display progress.
	mediainfo_command = "mediainfo --Inform='Video;%FrameCount%' \"" + track_metadata.file_name + "\""
	print(mediainfo_command)
	process = subprocess.Popen(mediainfo_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0:
		print("Calling Mediainfo on {file_name} failed with exit code {exit_code}.".format(file_name=track_metadata.file_name, exit_code=exit_code))
		num_frames = 0
	else:
		num_frames = int(cout.decode("utf-8"))

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
		},
		"dvd": {
			"preset": "8",
			"bitrate": "600",
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
	if preset == "dvd":
		if track_metadata.interlaced:
			if track_metadata.interlace_field_order == "tff":
				vsscript = "dvd_tff"
			else:
				vsscript = "dvd_bff"
			num_frames *= 2
		else:
			vsscript = "dvd_noninterlaced"
	else:
		vsscript = preset
	script_source = vsscript + ".vpy"
	try:
		with open(os.path.join(os.path.split(__file__)[0], script_source)) as f:
			script = f.read()
		script = script.format(input_file=track_metadata.file_name)
		with open(vapoursynth_script, "w") as f:
			f.write(script)

		vspipe_command = ["vspipe", "--y4m", vapoursynth_script, "-"]
		x265_command = [
			"x265",
			"-",
			"--y4m",
			"--fps", str(track_metadata.fps),
			"--sar", track_metadata.pixel_aspect_ratio,
			"--preset", x265_presets[preset]["preset"],
			"--bitrate", x265_presets[preset]["bitrate"],
			"--deblock", x265_presets[preset]["deblock"],
			"-b", "12",
			"--psy-rd", "0.4",
			"--aq-strength", "0.5",
			"--stats", stats_file
		]
		if num_frames != 0:
			x265_command.append("--frames")
			x265_command.append(str(num_frames))
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

def mux_mkv(tracks, attachments, guid, input_filename):
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

def ffmpeg(*options):
	"""
	Call upon FFMPEG to transcode something.
	:param options: The parameters to the FFMPEG call.
	"""
	ffmpeg_command = ["ffmpeg"] + list(options)
	print("Calling FFMPEG:", " ".join(ffmpeg_command))

	process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0: #0 is success.
		raise Exception("Calling FFmpeg failed with exit code {exit_code}. CERR: {cerr} . COUT: {cout}".format(exit_code=exit_code, cerr=str(cerr), cout=str(cout)))
