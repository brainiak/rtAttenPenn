import os
import ssl
import time
import json
import logging
import websocket
from base64 import b64encode
from pathlib import Path
from rtfMRI.fileWatcher import FileWatcher
from rtfMRI.utils import DebugLevels, findNewestFile
from rtfMRI.Errors import StateError


defaultAllowedDirs = ['/data']
defaultAllowedTypes = ['.dcm', '.mat']


class WebSocketFileWatcher:
    ''' A server that watches for files on the scanner computer and replies to
        cloud service requests with the file data.
    '''
    fileWatcher = FileWatcher()
    allowedDirs = None
    allowedTypes = None

    @staticmethod
    def runFileWatcher(serverAddr, retryInterval=10, allowedDirs=defaultAllowedDirs,
                       allowedTypes=defaultAllowedTypes):
        WebSocketFileWatcher.allowedDirs = allowedDirs
        for i in range(len(allowedTypes)):
            if not allowedTypes[i].startswith('.'):
                allowedTypes[i] = '.' + allowedTypes[i]
        WebSocketFileWatcher.allowedTypes = allowedTypes
        # go into loop trying to do webSocket connection periodically
        while True:
            try:
                wsAddr = os.path.join('wss://', serverAddr, 'wsData')
                logging.log(DebugLevels.L6, "Trying connection: %s", wsAddr)
                ws = websocket.WebSocketApp(wsAddr,
                                            on_message=WebSocketFileWatcher.on_message,
                                            on_error=WebSocketFileWatcher.on_error)
                logging.log(DebugLevels.L1, "Connected to: %s", wsAddr)
                # TODO - I don't really like setting this CERT_NONE option,
                #   it'd be better to somehow recognize the certificate
                ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
            except Exception as err:
                logging.log(logging.INFO, "WSFileWatcher Exception: %s", str(err))
            time.sleep(retryInterval)

    @staticmethod
    def on_message(client, message):
        fileWatcher = WebSocketFileWatcher.fileWatcher
        response = {'status': 400, 'error': 'unhandled request'}
        try:
            request = json.loads(message)
            cmd = request['cmd']
            if cmd == 'initWatch':
                dir = request['dir']
                filePattern = request['filePattern']
                minFileSize = request['minFileSize']
                logging.log(DebugLevels.L3, "initWatch: %s, %s, %d", dir, filePattern, minFileSize)
                if dir is None or filePattern is None or minFileSize is None:
                    errStr = "InitWatch: Missing file information: {} {}".format(dir, filePattern)
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                elif WebSocketFileWatcher.validateRequestedFile(dir, None) is False:
                    errStr = 'InitWatch: Non-allowed directory {}'.format(dir)
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                elif not os.path.exists(dir):
                    errStr = 'InitWatch: No such directory: {}'.format(dir)
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                else:
                    fileWatcher.initFileNotifier(dir, filePattern, minFileSize)
                    response = {'status': 200}
            elif cmd == 'watchFile':
                filename = request['filename']
                timeout = request['timeout']
                logging.log(DebugLevels.L3, "watchFile: %s", filename)
                if filename is None:
                    errStr = 'WatchFile: Missing filename'
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                elif WebSocketFileWatcher.validateRequestedFile(None, filename) is False:
                    errStr = 'WatchFile: Non-allowed file {}'.format(filename)
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                else:
                    retVal = fileWatcher.waitForFile(filename, timeout=timeout)
                    if retVal is None:
                        errStr = "WatchFile: 408 Timeout {}s: {}".format(timeout, filename)
                        response = {'status': 408, 'error': errStr}
                        logging.log(logging.WARNING, errStr)
                    else:
                        with open(filename, 'rb') as fp:
                            data = fp.read()
                        b64Data = b64encode(data)
                        b64StrData = b64Data.decode('utf-8')
                        response = {'status': 200, 'filename': filename, 'data': b64StrData}
            elif cmd == 'getFile':
                filename = request['filename']
                if not os.path.isabs(filename):
                    # relative path to the watch dir
                    filename = os.path.join(fileWatcher.watchDir, filename)
                logging.log(DebugLevels.L3, "getFile: %s", filename)
                if filename is None:
                    errStr = "GetFile: Missing filename"
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                elif WebSocketFileWatcher.validateRequestedFile(None, filename) is False:
                    errStr = 'GetFile: Non-allowed file {}'.format(filename)
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                elif not os.path.exists(filename):
                    errStr = "GetFile: File not found {}".format(filename)
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                else:
                    with open(filename, 'rb') as fp:
                        data = fp.read()
                    b64Data = b64encode(data)
                    b64StrData = b64Data.decode('utf-8')
                    response = {'status': 200, 'filename': filename, 'data': b64StrData}
            elif cmd == 'getNewestFile':
                filename = request['filename']
                logging.log(DebugLevels.L3, "getNewestFile: %s", filename)
                if filename is None:
                    errStr = "GetNewestFile: Missing filename"
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                elif WebSocketFileWatcher.validateRequestedFile(None, filename) is False:
                    errStr = 'GetNewestFile: Non-allowed file {}'.format(filename)
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                else:
                    baseDir, filePattern = os.path.split(filename)
                    if not os.path.isabs(baseDir):
                        # relative path to the watch dir
                        baseDir = os.path.join(fileWatcher.watchDir, baseDir)
                    filename = findNewestFile(baseDir, filePattern)
                    if filename is None or not os.path.exists(filename):
                        errStr = 'GetNewestFile: file not found: {}'.format(os.path.join(baseDir, filePattern))
                        response = {'status': 400, 'error': errStr}
                        logging.log(logging.WARNING, errStr)
                    else:
                        with open(filename, 'rb') as fp:
                            data = fp.read()
                        b64Data = b64encode(data)
                        b64StrData = b64Data.decode('utf-8')
                        response = {'status': 200, 'filename': filename, 'data': b64StrData}
            elif cmd == 'ping':
                response = {'status': 200}
            elif cmd == 'putTextFile':
                filename = request['filename']
                text = request['text']
                logging.log(DebugLevels.L3, "putTextFile: %s", filename)
                if filename is None:
                    errStr = 'PutTextFile: Missing filename field'
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                elif text is None:
                    errStr = 'PutTextFile: Missing text field'
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                elif WebSocketFileWatcher.validateRequestedFile(None, filename, textFileTypeOnly=True) is False:
                    errStr = 'PutTextFile: Non-allowed file {}'.format(filename)
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                elif type(text) is not str:
                    errStr = "PutTextFile: Only text allowed"
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                else:
                    outputDir = os.path.dirname(filename)
                    if not os.path.exists(outputDir):
                        os.makedirs(outputDir)
                    # print('putTextFile: write {}'.format(filename))
                    with open(filename, 'w+') as volFile:
                        volFile.write(text)
                    response = {'status': 200}
            elif cmd == 'dataLog':
                    filename = request['filename']
                    logging.log(DebugLevels.L3, "dataLog: %s", filename)
                    logLine = request['logLine']
                    if filename is None:
                        errStr = 'DataLog: Missing filename field'
                        response = {'status': 400, 'error': errStr}
                        logging.log(logging.WARNING, errStr)
                    elif logLine is None:
                        errStr = 'DataLog: Missing logLine field'
                        response = {'status': 400, 'error': errStr}
                        logging.log(logging.WARNING, errStr)
                    elif WebSocketFileWatcher.validateRequestedFile(None, filename, textFileTypeOnly=True) is False:
                        errStr = 'DataLog: Non-allowed file {}'.format(filename)
                        response = {'status': 400, 'error': errStr}
                        logging.log(logging.WARNING, errStr)
                    else:
                        with open(filename, 'a+') as logFile:
                            logFile.write(logLine + '\n')
                        response = {'status': 200}
            else:
                errStr = 'OnMessage: Unrecognized command {}'.format(cmd)
                response = {'status': 400, 'error': errStr}
                logging.log(logging.WARNING, errStr)
        except Exception as err:
            errStr = "OnMessage Exception: {}: {}".format(cmd, err)
            logging.log(logging.WARNING, errStr)
            response = {'status': 400, 'error': errStr}
        # merge response into the request dictionary
        request.update(response)
        response = request
        client.send(json.dumps(response))

    @staticmethod
    def validateRequestedFile(dir, file, textFileTypeOnly=False):
        # Restrict requests to certain directories and file types
        if WebSocketFileWatcher.allowedDirs is None or WebSocketFileWatcher.allowedTypes is None:
            raise StateError('Allowed Directories or File Types is not set')
        if file is not None and file != '':
            fileDir, filename = os.path.split(file)
            fileExtension = Path(filename).suffix
            if textFileTypeOnly:
                if fileExtension != '.txt':
                    return False
            elif fileExtension not in WebSocketFileWatcher.allowedTypes:
                return False
            if fileDir is not None and fileDir != '':  # and os.path.isabs(fileDir):
                dirMatch = False
                for allowedDir in WebSocketFileWatcher.allowedDirs:
                    if fileDir.startswith(allowedDir):
                        dirMatch = True
                        break
                if dirMatch is False:
                    return False
        if dir is not None and dir != '':
            for allowedDir in WebSocketFileWatcher.allowedDirs:
                if dir.startswith(allowedDir):
                    return True
            return False
        # default case
        return True

    @staticmethod
    def on_error(client, error):
        logging.log(logging.WARNING, "on_error: WSFileWatcher: %s", error)
