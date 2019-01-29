#!/usr/bin/env bash

pushd webInterface/rtAtten/web
browserify src/tabs.js -o build/tabsBundle.js -t [ babelify --presets [ @babel/preset-env @babel/preset-react ] ]
popd

python fileWatchServer.py -s localhost:8888 -i 5 &
PID=$!

# check if experiment file is supplied with -e filename
EXP_PARAM=''
if [ $# -gt 1 ]; then
  EXP_PARAM="$1 $2"
fi

python WebMain.py -l -r $EXP_PARAM

kill -15 $PID
