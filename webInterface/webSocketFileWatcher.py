import os
import sys
import time
import json
import logging
import threading
import getpass
import requests
import websocket
from base64 import b64encode
from pathlib import Path
from rtfMRI.fileWatcher import FileWatcher
from rtfMRI.utils import DebugLevels, findNewestFile
from rtfMRI.Errors import StateError

defaultAllowedDirs = ['/data']
defaultAllowedTypes = ['.dcm', '.mat']
certFile = 'certs/rtAtten.crt'


class WebSocketFileWatcher:
    ''' A server that watches for files on the scanner computer and replies to
        cloud service requests with the file data.
    '''
    fileWatcher = FileWatcher()
    allowedDirs = None
    allowedTypes = None
    serverAddr = None
    sessionCookie = None
    needLogin = True
    shouldExit = False
    # Synchronizing across threads
    clientLock = threading.Lock()
    fileWatchLock = threading.Lock()

    @staticmethod
    def runFileWatcher(serverAddr, retryInterval=10, allowedDirs=defaultAllowedDirs,
                       allowedTypes=defaultAllowedTypes, username=None, password=None):
        WebSocketFileWatcher.serverAddr = serverAddr
        WebSocketFileWatcher.allowedDirs = allowedDirs
        for i in range(len(allowedTypes)):
            if not allowedTypes[i].startswith('.'):
                allowedTypes[i] = '.' + allowedTypes[i]
        WebSocketFileWatcher.allowedTypes = allowedTypes
        # go into loop trying to do webSocket connection periodically
        while not WebSocketFileWatcher.shouldExit:
            if WebSocketFileWatcher.needLogin or WebSocketFileWatcher.sessionCookie is None:
                WebSocketFileWatcher.login(username, password)
            try:
                wsAddr = os.path.join('wss://', serverAddr, 'wsData')
                logging.log(DebugLevels.L6, "Trying connection: %s", wsAddr)
                ws = websocket.WebSocketApp(wsAddr,
                                            on_message=WebSocketFileWatcher.on_message,
                                            on_close=WebSocketFileWatcher.on_close,
                                            on_error=WebSocketFileWatcher.on_error,
                                            cookie="login="+WebSocketFileWatcher.sessionCookie)
                logging.log(DebugLevels.L1, "Connected to: %s", wsAddr)
                ws.run_forever(sslopt={"ca_certs": certFile})
            except Exception as err:
                logging.log(logging.INFO, "WSFileWatcher Exception: %s", str(err))
            if not WebSocketFileWatcher.needLogin:
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
                    WebSocketFileWatcher.fileWatchLock.acquire()
                    try:
                        fileWatcher.initFileNotifier(dir, filePattern, minFileSize)
                    finally:
                        WebSocketFileWatcher.fileWatchLock.release()
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
                    WebSocketFileWatcher.fileWatchLock.acquire()
                    try:
                        retVal = fileWatcher.waitForFile(filename, timeout=timeout)
                    finally:
                        WebSocketFileWatcher.fileWatchLock.release()
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
                if filename is not None and not os.path.isabs(filename):
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
            elif cmd == 'error':
                errorCode = request['status']
                if errorCode == 401:
                    WebSocketFileWatcher.needLogin = True
                    WebSocketFileWatcher.sessionCookie = None
                errStr = 'Error {}: {}'.format(errorCode, request['error'])
                logging.log(logging.ERROR, request['error'])
                return
            else:
                errStr = 'OnMessage: Unrecognized command {}'.format(cmd)
                response = {'status': 400, 'error': errStr}
                logging.log(logging.WARNING, errStr)
        except Exception as err:
            errStr = "OnMessage Exception: {}: {}".format(cmd, err)
            logging.log(logging.WARNING, errStr)
            response = {'status': 400, 'error': errStr}
            if cmd == 'error':
                sys.exit()
        # merge response into the request dictionary
        request.update(response)
        response = request
        WebSocketFileWatcher.clientLock.acquire()
        try:
            client.send(json.dumps(response))
        finally:
            WebSocketFileWatcher.clientLock.release()

    @staticmethod
    def on_close(client):
        logging.info('connection closed')

    @staticmethod
    def on_error(client, error):
        if type(error) is KeyboardInterrupt:
            WebSocketFileWatcher.shouldExit = True
        else:
            logging.log(logging.WARNING, "on_error: WSFileWatcher: {} {}".
                        format(type(error), str(error)))

    @staticmethod
    def login(username, password):
        if username is None or password is None:
            print('Login required...')
            username = input('Username: ')
            password = getpass.getpass()
        loginURL = os.path.join('https://', WebSocketFileWatcher.serverAddr, 'login')
        session = requests.Session()
        session.verify = certFile
        getResp = session.get(loginURL)
        if getResp.status_code != 200:
            raise requests.HTTPError('Get URL: {}, returned {}'.format(loginURL, getResp.status_code))
        postData = {'name': username, 'password': password, '_xsrf': session.cookies['_xsrf']}
        postResp = session.post(loginURL, postData)
        if postResp.status_code != 200:
            raise requests.HTTPError('Post URL: {}, returned'.format(loginURL, getResp.status_code))
        WebSocketFileWatcher.sessionCookie = session.cookies['login']

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
