#!/usr/bin/env python

import argparse  # To receive the argument of which directory to watch.
import functools  # To start a thread with a parameter.
import os  # To walk the files recursively.
import threading  # To have a consuming thread process the files coming in.
import time  # To sleep the producing thread.

import encode  # The module that will do the actual work of transcoding.

def rescan(directory, todo):
	for root, dirs, files in os.walk(directory):
		dirs[:] = [d for d in dirs if os.path.join(root, d) != os.path.join(directory, "output")]  # Ignore output directory.
		for file in files:
			todo.add(os.path.join(root, file))

def process_thread(prefix, todo):
	while True:  # Wait indefinitely for files to arrive in this thread.
		while len(todo) > 0:
			input_filename = todo.pop()
			relative_path = input_filename[len(prefix) + 1:]
			output_filename = os.path.join(prefix, "output", relative_path)
			preset = relative_path[:relative_path.find(os.path.sep)]
			try:
				encode.process(input_filename, output_filename, preset)
			except Exception as e:
				print(e)
		time.sleep(10)  # Don't spinloop! Just poll every 10 seconds.

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Look for files to transcode.")
	parser.add_argument("watch_directory", metavar="directory", type=str, help="The directory to transcode files in.")
	args = parser.parse_args()

	todo = set()

	consumer_thread = threading.Thread(target=functools.partial(process_thread, args.watch_directory, todo))
	consumer_thread.start()
	# This becomes the producer thread then.

	while True:
		rescan(args.watch_directory, todo)
		time.sleep(10)