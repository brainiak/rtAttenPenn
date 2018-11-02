#!/usr/bin/env bash

pushd rtAtten/web
browserify src/tabs.js -o build/tabsBundle.js -t [ babelify --presets [ @babel/preset-env @babel/preset-react ] ]
popd

python -s fileWatchServer.py -s localhost:8888 -i 5 &
PID=$!

# check if experiment file is supplied with -e filename
EXP_PARAM=''
if [ $# -gt 1 ]; then
  EXP_PARAM="$1 $2"
fi

python ClientMain.py -w -l $EXP_PARAM

kill -15 $PID
