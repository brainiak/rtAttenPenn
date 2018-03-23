#!/usr/bin/bash
rm rtfMRI*
randNum=$RANDOM
openssl req -newkey rsa:2048 -nodes -keyout rtfMRI_rsa-$randNum.private -x509 -days 365 -out rtfMRI-$randNum.crt \
  -subj "/C=US/ST=New Jersey/L=Princeton/O=Princeton University/CN=rtAtten"; \
ln -s rtfMRI_rsa-$randNum.private rtfMRI_rsa.private; \
ln -s rtfMRI-$randNum.crt rtfMRI.crt
