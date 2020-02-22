#!/usr/bin/env python

import argparse  # To receive the argument of which directory to watch.
import functools  # To start a thread with a parameter.
import os  # To walk the files recursively.
import threading  # To have a consuming thread process the files coming in.
import time  # To sleep the producing thread.

def rescan(directory, todo):
	for root, dirs, files in os.walk(directory):
		dirs[:] = [d for d in dirs if os.path.join(root, d) != os.path.join(directory, "output")]  # Ignore output directory.
		for file in files:
			print("file: ", os.path.join(root, file))
			todo.add(os.path.join(root, file))

def process_thread(todo):
	while True:
		while len(todo) > 0:
			print(todo.pop())

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Look for files to transcode.")
	parser.add_argument("watch_directory", metavar="directory", type=str, help="The directory to transcode files in.")
	args = parser.parse_args()

	todo = set()

	consumer_thread = threading.Thread(target=functools.partial(process_thread, todo))
	consumer_thread.start()
	# This becomes the producer thread then.

	while True:
		rescan(args.watch_directory, todo)
		time.sleep(10)