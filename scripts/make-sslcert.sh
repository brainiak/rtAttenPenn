#!/bin/bash

if [ ! $# == 1 ]; then
    echo "Usage: $0 ip_address"
    exit
fi

IP_ADDRESS=$1

SUBJ_ALT_NAME="subjectAltName=DNS.1:princeton.edu,DNS.2:localhost,IP.1:$IP_ADDRESS"

echo $SUBJ_ALT_NAME

openssl req -x509 -key certs/rtAtten_private.key -sha256 -days 3650 -nodes -out certs/rtAtten.crt -extensions san -config <(echo '[req]'; echo 'distinguished_name=req'; echo '[san]'; echo $SUBJ_ALT_NAME) -subj '/C=US/ST=New Jersey/L=Princeton/O=Princeton University/OU=PNI/CN=rtAtten.princeton.edu'
