#!/usr/bin/env bash

inotifywait -e moved_to,create -m --exclude "$1/output" "$1" |
while read -r directory events filename; do
	python3 $(dirname "$0")/encode.py "$directory/$filename" "$1/output/$filename"
done
