#!/usr/bin/env python

import argparse #To parse command line arguments.
import os.path #To parse file names (used for file type detection).
import shutil #To move files.
import subprocess #To call the encoders and muxers.
import uuid #To rename files to something that doesn't exist yet.

parser = argparse.ArgumentParser(description="Re-encode videos.")
parser.add_argument("input_filename", metavar="input", type=str, help="The input file name to encode.")
parser.add_argument("--preset", dest="preset", type=str, help="Preset for encoding. Must be one of: 'sd', 'hd', 'animated'")
args = parser.parse_args()
input_filename = args.input_filename
preset = args.preset

guid = uuid.uuid4().hex #A new file name that is almost guaranteed to not exist yet.
extension = os.path.splitext(input_filename)[1]
shutil.move(input_filename, guid + extension)

if extension == ".mkv":
	in_mkv = guid + ".mkv"
	#Find the tracks and attachments in the MKV file.
	process = subprocess.Popen(["mkvinfo", in_mkv], stdout=PIPE)
	(cout, cerr) = process.communicate()
	exit_code = process.wait()
	if exit_code != 0:
		raise Exception("Calling MKVInfo failed with exit code {exit_code}. CERR: {cerr}".format(exit_code=exit_code, cerr=cerr))
	print(cout) #Debug.
else:
	raise Exception("Unknown file extension: {extension}".format(extension=extension))
