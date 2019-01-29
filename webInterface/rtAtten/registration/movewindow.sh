#!/bin/bash

function move_window {
  echo "move_window sleeping 10s"
  sleep 10
  # Get the window IDs for commands matching the name
  WIDS=$(xdotool search --onlyvisible --name $1)
  # Separate the window IDs in an array
  IFS=' ' read -a WID_ARRAY <<< $WIDS
  # Get the last element in the array, i.e. the window most recently opened
  WID=${WID_ARRAY[-1]}
  #echo "WIDS $WIDS"
  #echo "WID_ARRAY ${WID_ARRAY[*]}"
  #echo "WID Is $WID"
  # Set the position and size of the desired window
  xdotool windowmove $WID 0 0
  xdotool windowsize $WID 1024 768
}

# Check if fsleyes command is available and fallback to fslview
VIEWCMD=fsleyes
if ! [ -x "$(command -v fsleyes)" ]; then
  VIEWCMD=fslview
fi
