import os
import sys
import re
import json
import logging
import getpass
import requests
from pathlib import Path
from base64 import b64decode
import rtfMRI.utils as utils
from rtfMRI.StructDict import StructDict
from rtfMRI.ReadDicom import readDicomFromBuffer
from rtfMRI.Errors import RequestError, StateError
from requests.packages.urllib3.contrib import pyopenssl

certFile = 'certs/rtAtten.crt'


# Set of helper functions for creating remote file requests
def getFileReqStruct(filename, writefile=False):
    cmd = {'cmd': 'getFile', 'route': 'dataserver', 'filename': filename}
    if writefile is True:
        cmd['writefile'] = True
    return cmd


def getNewestFileReqStruct(filename, writefile=False):
    cmd = {'cmd': 'getNewestFile', 'route': 'dataserver', 'filename': filename}
    if writefile is True:
        cmd['writefile'] = True
    return cmd


def watchFileReqStruct(filename, timeout=5, writefile=False):
    cmd = {'cmd': 'watchFile', 'route': 'dataserver', 'filename': filename, 'timeout': timeout}
    if writefile is True:
        cmd['writefile'] = True
    return cmd


def initWatchReqStruct(dir, filePattern, minFileSize):
    cmd = {
        'cmd': 'initWatch',
        'route': 'dataserver',
        'dir': dir,
        'filePattern': filePattern,
        'minFileSize': minFileSize
    }
    return cmd


def putTextFileReqStruct(filename, str):
    cmd = {
        'cmd': 'putTextFile',
        'route': 'dataserver',
        'filename': filename,
        'text': str,
    }
    return cmd


def clientWebpipeCmd(webpipes, cmd):
    '''Send a web request using named pipes to the web server for handling.
    This allows a separate client process to make requests of the web server process.
    It writes the request on fd_out and recieves the reply on fd_in.
    '''
    webpipes.fd_out.write(json.dumps(cmd) + os.linesep)
    msg = webpipes.fd_in.readline()
    if len(msg) == 0:
        # fifo closed
        raise StateError('WebPipe closed')
    response = json.loads(msg)
    retVals = StructDict()
    decodedData = None
    if 'status' not in response:
        raise StateError('clientWebpipeCmd: status not in response: {}'.format(response))
    retVals.statusCode = response['status']
    if retVals.statusCode == 200:  # success
        if 'filename' in response:
            retVals.filename = response['filename']
        if 'data' in response:
            decodedData = b64decode(response['data'])
            if retVals.filename is None:
                raise StateError('clientWebpipeCmd: filename field is None')
            retVals.data = formatFileData(retVals.filename, decodedData)
    elif retVals.statusCode not in (200, 408):
        raise RequestError('WebRequest error: status {}: {}'.format(retVals.statusCode, response['error']))
    return retVals


def formatFileData(filename, data):
    '''Convert raw bytes to a specific memory format such as dicom or matlab data'''
    fileExtension = Path(filename).suffix
    if fileExtension == '.mat':
        # Matlab file format
        result = utils.loadMatFileFromBuffer(data)
    elif fileExtension == '.dcm':
        # Dicom file format
        result = readDicomFromBuffer(data)
    else:
        result = data
    return result


def login(serverAddr, username, password):
    loginURL = os.path.join('https://', serverAddr, 'login')
    session = requests.Session()
    session.verify = certFile
    try:
        getResp = session.get(loginURL)
    except Exception as err:
        raise ConnectionError('Connection error: {}'.format(loginURL))
    if getResp.status_code != 200:
        raise requests.HTTPError('Get URL: {}, returned {}'.format(loginURL, getResp.status_code))
    if username is None:
        print('Login required...')
        username = input('Username: ')
        password = getpass.getpass()
    elif password is None:
        password = getpass.getpass()
    postData = {'name': username, 'password': password, '_xsrf': session.cookies['_xsrf']}
    postResp = session.post(loginURL, postData)
    if postResp.status_code != 200:
        raise requests.HTTPError('Post URL: {}, returned {}'.format(loginURL, postResp.status_code))
    return session.cookies['login']


def checkSSLCertAltName(certFilename, altName):
    with open(certFilename, 'r') as fh:
        certData = fh.read()
    x509 = pyopenssl.OpenSSL.crypto.load_certificate(pyopenssl.OpenSSL.crypto.FILETYPE_PEM, certData)
    altNames = pyopenssl.get_subj_alt_name(x509)
    for _, name in altNames:
        if altName == name:
            return True
    return False


def makeSSLCertFile(serverName):
    logging.info('create sslCert')
    cmd = 'bash scripts/make-sslcert.sh '
    if re.match('^[0-9*]+\.', serverName):
        cmd += ' -ip ' + serverName
    else:
        cmd += ' -url ' + serverName
    success = utils.runCmdCheckOutput(cmd.split(), 'certified until')
    if not success:
        print('Failed to make certificate:')
        sys.exit()
