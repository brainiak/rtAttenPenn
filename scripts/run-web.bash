#!/usr/bin/env bash

pushd rtAtten/web
browserify src/tabs.js -o build/tabsBundle.js
popd

python -s rtfMRI/scripts/fileWatchServer.py -s localhost:8888 -i 5 &
PID=$!

# check if experiment file is supplied with -e filename
EXP_PARAM=''
if [ $# -gt 1 ]; then
  EXP_PARAM="$1 $2"
fi

python rtfMRI/scripts/ClientMain.py -w -l $EXP_PARAM

kill -15 $PID
