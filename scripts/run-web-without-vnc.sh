#!/usr/bin/env bash

pushd webInterface/rtAtten/web
npm run build
popd

# check if experiment file is supplied with -e filename
EXP_PARAM=''
if [ $# -gt 1 ]; then
  EXP_PARAM="$1 $2"
fi

python WebMain.py -l -r $EXP_PARAM
