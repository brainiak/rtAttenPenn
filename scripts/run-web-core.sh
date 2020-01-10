#!/usr/bin/env bash

# get commandline params
while test $# -gt 0
do
  case "$1" in
    -h)
      echo "$0 [-e <toml_file>] [-ip <local_ip_or_hostname] [--localfiles]"
      exit 0
      ;;
    -e) CFG=$2
      ;;
    -ip) IP=$2
      ;;
    --server) REMOTESERVER=$2
      ;;
    --localfiles) USELOCALFILES=1
      ;;
  esac
  shift
done

# check if experiment file is supplied with -e filename
CFG_PARAM=''
if [ ! -z $CFG ]; then
  CFG_PARAM="-e $CFG"
fi

R_PARAM=''
if [ -z $USELOCALFILES ]; then
  # USELOCALFILES not set, use remote files
  R_PARAM='-r'
fi

S_PARAM=''
if [ -z $REMOTESERVER ]; then
  # REMOTESERVER not set, start classification server locally
  S_PARAM='-l'
else
  S_PARAM="-s $REMOTESERVER"
fi

# Check if face and scene image directories exist
if [[ ! -d 'webInterface/images/FACE_NEUTRAL' || ! -d 'webInterface/images/FACE_NEGATIVE' || ! -d 'webInterface/images/SCENE' ]] ; then
    echo "Expecting feedback images in ./webInterface/images/FACE_NEUTRAL,  ./webInterface/images/FACE_NEGATIVE and ./webInterface/images/SCENE"
    echo "Please create those directories, exiting ..."
    exit -1
fi

pushd webInterface/rtAtten/web
npm run build
npm run buildSubj
popd

# activate conda python env
source ~/.bashrc
conda deactivate
conda activate rtAtten

if [ -z $IP ]; then
  echo "Warning: no ip address supplied, credentials won't be updated"
else
  bash scripts/make-sslcert.sh -ip $IP
fi

python WebMain.py -f 'webInterface/images' $S_PARAM $R_PARAM $CFG_PARAM
