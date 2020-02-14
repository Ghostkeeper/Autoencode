#!/usr/bin/env bash

inotifywait -r -e moved_to,close_write -m --exclude "$1/output" --format "%e %w%f" "$1" |
  while read events filepath; do
    name="$(echo $filepath | cut -d'/' -f6-)"
    python3 $(dirname "$0")/encode.py "$1/$name" "$1/output/$name" --preset "$(echo $name | cut -d'/' -f1)"
  done
