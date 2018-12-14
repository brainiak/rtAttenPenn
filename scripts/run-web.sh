#!/usr/bin/env bash

pushd rtAtten/web
npm run build
popd

# check if experiment file is supplied with -e filename
EXP_PARAM=''
if [ $# -gt 1 ]; then
  EXP_PARAM="$1 $2"
fi

python ClientMain.py -w -l $EXP_PARAM
