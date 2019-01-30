import os
import json
from pathlib import Path
from base64 import b64decode
import rtfMRI.utils as utils
from rtfMRI.StructDict import StructDict
from rtfMRI.ReadDicom import readDicomFromBuffer
from rtfMRI.Errors import RequestError, StateError


# Set of helper functions for creating remote file requests
def getFileReqStruct(filename, writefile=False):
    cmd = {'cmd': 'getFile', 'filename': filename}
    if writefile is True:
        cmd['writefile'] = True
    return cmd


def getNewestFileReqStruct(filename, writefile=False):
    cmd = {'cmd': 'getNewestFile', 'filename': filename}
    if writefile is True:
        cmd['writefile'] = True
    return cmd


def watchFileReqStruct(filename, timeout=10, writefile=False):
    cmd = {'cmd': 'watchFile', 'filename': filename, 'timeout': timeout}
    if writefile is True:
        cmd['writefile'] = True
    return cmd


def initWatchReqStruct(dir, filePattern, minFileSize):
    cmd = {
        'cmd': 'initWatch',
        'dir': dir,
        'filePattern': filePattern,
        'minFileSize': minFileSize
    }
    return cmd


def putTextFileReqStruct(filename, str):
    cmd = {
        'cmd': 'putTextFile',
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
        raise RequestError('WebRequest error: ' + response['error'])
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
