import os
import sys
import ssl
import time
import json
import logging
import threading
import websocket
from base64 import b64encode
from queue import Queue, Empty
from pathlib import Path
from watchdog.events import PatternMatchingEventHandler  # type: ignore
from rtfMRI.utils import DebugLevels, findNewestFile
from rtfMRI.Errors import StateError


class FileWatcher():
    def __new__(cls):
        if sys.platform in ("linux", "linux2"):
            # create linux version
            newcls = InotifyFileWatcher.__new__(InotifyFileWatcher)
            newcls.__init__()
            return newcls
        elif sys.platform in ("darwin", "win32"):
            # create Mac/Windows version
            newcls = WatchdogFileWatcher.__new__(WatchdogFileWatcher)
            newcls.__init__()
            return newcls
        else:
            # unsupported os type
            logging.log(logging.ERROR, "Unsupported os type %s" % (sys.platform))
            return None

    def __init__(self):
        logging.log(logging.ERROR, "FileWatcher is abstract class. __init__ not implemented")

    def __del__(self):
        logging.log(logging.ERROR, "FileWatcher is abstract class. __del__ not implemented")

    def initFileNotifier(self, dir, filePattern, minFileSize):
        logging.log(logging.ERROR, "FileWatcher is abstract class. initFileNotifier not implemented")

    def waitForFile(self, specificFileName, timeout=0):
        logging.log(logging.ERROR, "FileWatcher is abstract class. waitForFile not implemented")


if sys.platform in ("darwin", "win32"):
    from watchdog.observers import Observer  # type: ignore


# Version of FileWatcher for Mac and Windows
class WatchdogFileWatcher():
    def __init__(self):
        self.observer = None
        self.fileNotifyHandler = None
        self.fileNotifyQ = Queue()  # type: None
        self.filePattern = None
        self.watchDir = None
        self.minFileSize = 0

    def __del__(self):
        if self.observer is not None:
            try:
                self.observer.stop()
            except Exception as err:
                logging.log(logging.INFO, "FileWatcher: oberver.stop(): %s", str(err))

    def initFileNotifier(self, dir, filePattern, minFileSize):
        self.minFileSize = minFileSize
        if self.observer is not None:
            self.observer.stop()
        self.observer = Observer()
        if filePattern is None or filePattern == '':
            filePattern = '*'
        self.filePattern = filePattern
        self.watchDir = dir
        self.fileNotifyHandler = FileNotifyHandler(self.fileNotifyQ, [filePattern])
        self.observer.schedule(self.fileNotifyHandler, dir, recursive=False)
        self.observer.start()

    def waitForFile(self, specificFileName, timeout=0):
        fileExists = os.path.exists(specificFileName)
        if not fileExists:
            if self.observer is None:
                raise FileNotFoundError("No fileNotifier and dicom file not found %s" % (specificFileName))
            else:
                logStr = "FileWatcher: Waiting for file {}, timeout {}s ".format(specificFileName, timeout)
                logging.log(DebugLevels.L6, logStr)
        eventLoopCount = 0
        exitWithFileEvent = False
        eventTimeStamp = 0
        startTime = time.time()
        timeToCheckForFile = time.time() + 1  # check if file exists at least every second
        while not fileExists:
            if timeout > 0 and time.time() > (startTime + timeout):
                return None
            # look for file creation event
            eventLoopCount += 1
            try:
                event, ts = self.fileNotifyQ.get(block=True, timeout=1.0)
            except Empty as err:
                # The timeout occured on fileNotifyQ.get()
                fileExists = os.path.exists(specificFileName)
                continue
            assert event is not None
            # We may have a stale event from a previous file if multiple events
            #   are created per file or if the previous file eventloop
            #   timed out and then the event arrived later.
            if event.src_path == specificFileName:
                fileExists = True
                exitWithFileEvent = True
                eventTimeStamp = ts
                continue
            if time.time() > timeToCheckForFile:
                # periodically check if file exists, can occur if we get
                #   swamped with unrelated events
                fileExists = os.path.exists(specificFileName)
                timeToCheckForFile = time.time() + 1

        # wait for the full file to be written, wait at most 200 ms
        fileSize = 0
        totalWriteWait = 0.0
        waitIncrement = 0.01
        while fileSize < self.minFileSize and totalWriteWait <= 0.3:
            time.sleep(waitIncrement)
            totalWriteWait += waitIncrement
            fileSize = os.path.getsize(specificFileName)
        logging.log(DebugLevels.L6,
                    "File avail: eventLoopCount %d, writeWaitTime %.3f, "
                    "fileEventCaptured %s, fileName %s, eventTimeStamp %.5f",
                    eventLoopCount, totalWriteWait,
                    exitWithFileEvent, specificFileName, eventTimeStamp)
        return specificFileName


class FileNotifyHandler(PatternMatchingEventHandler):  # type: ignore
    def __init__(self, q, patterns):
        super().__init__(patterns=patterns)
        self.q = q

    def on_created(self, event):
        self.q.put((event, time.time()))

    def on_modified(self, event):
        self.q.put((event, time.time()))


# import libraries for Linux version
if sys.platform in ("linux", "linux2"):
    import inotify
    import inotify.adapters


# Version of FileWatcher for Linux
class InotifyFileWatcher():
    def __init__(self):
        self.watchDir = None
        self.shouldExit = False
        # create a listening thread
        self.fileNotifyQ = Queue()  # type: None
        self.notifier = inotify.adapters.Inotify()
        self.notify_thread = threading.Thread(name='inotify', target=self.notifyEventLoop)
        self.notify_thread.setDaemon(True)
        self.notify_thread.start()

    def __del__(self):
        self.shouldExit = True
        self.notify_thread.join(timeout=2)

    def initFileNotifier(self, dir, filePattern, minFileSize):
        # inotify doesn't use filepatterns
        assert dir is not None
        if not os.path.exists(dir):
            raise NotADirectoryError("No such directory: %s" % (dir))
        if dir != self.watchDir:
            if self.watchDir is not None:
                self.notifier.remove_watch(self.watchDir)
            self.watchDir = dir
            self.notifier.add_watch(self.watchDir, mask=inotify.constants.IN_CLOSE_WRITE)

    def waitForFile(self, specificFileName, timeout=0):
        fileExists = os.path.exists(specificFileName)
        if not fileExists:
            if self.notify_thread is None:
                raise FileNotFoundError("No fileNotifier and dicom file not found %s" % (specificFileName))
            else:
                logStr = "FileWatcher: Waiting for file {}, timeout {}s ".format(specificFileName, timeout)
                logging.log(DebugLevels.L6, logStr)
        eventLoopCount = 0
        exitWithFileEvent = False
        eventTimeStamp = 0
        startTime = time.time()
        timeToCheckForFile = time.time() + 1  # check if file exists at least every second
        while not fileExists:
            if timeout > 0 and time.time() > (startTime + timeout):
                return None
            # look for file creation event
            eventLoopCount += 1
            try:
                eventfile, ts = self.fileNotifyQ.get(block=True, timeout=1.0)
            except Empty as err:
                # The timeout occured on fileNotifyQ.get()
                fileExists = os.path.exists(specificFileName)
                continue
            assert eventfile is not None
            # We may have a stale event from a previous file if multiple events
            #   are created per file or if the previous file eventloop
            #   timed out and then the event arrived later.
            if eventfile == specificFileName:
                fileExists = True
                exitWithFileEvent = True
                eventTimeStamp = ts
                continue
            if time.time() > timeToCheckForFile:
                # periodically check if file exists, can occur if we get
                #   swamped with unrelated events
                fileExists = os.path.exists(specificFileName)
                timeToCheckForFile = time.time() + 1
        logging.log(DebugLevels.L6,
                    "File avail: eventLoopCount %d, fileEventCaptured %s, "
                    "fileName %s, eventTimeStamp %d", eventLoopCount,
                    exitWithFileEvent, specificFileName, eventTimeStamp)
        return specificFileName

    def notifyEventLoop(self):
        for event in self.notifier.event_gen():
            if self.shouldExit is True:
                break
            if event is not None:
                # print(event)      # uncomment to see all events generated
                if 'IN_CLOSE_WRITE' in event[1]:
                    fullpath = os.path.join(event[2], event[3])
                    self.fileNotifyQ.put((fullpath, time.time()))
                else:
                    self.fileNotifyQ.put(('', time.time()))


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
                logging.log(DebugLevels.L3, "init: %s, %s, %d", dir, filePattern, minFileSize)
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
                logging.log(DebugLevels.L3, "watch: %s", filename)
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
                        response = {'status': 200, 'data': b64StrData}
            elif cmd == 'getFile':
                filename = request['filename']
                if not os.path.isabs(filename):
                    # relative path to the watch dir
                    filename = os.path.join(fileWatcher.watchDir, filename)
                logging.log(DebugLevels.L3, "get: %s", filename)
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
                    response = {'status': 200, 'data': b64StrData}
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
                        response = {'status': 200, 'data': b64StrData}
            elif cmd == 'ping':
                response = {'status': 200}
            elif cmd == 'putTextFile':
                filename = request['filename']
                text = request['data']
                if filename is None:
                    errStr = 'PutTextFile: Missing filename field'
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                elif text is None:
                    errStr = 'PutTextFile: Missing data field'
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                elif WebSocketFileWatcher.validateRequestedFile(None, filename, textFileTypeOnly=True) is False:
                    errStr = 'PutTextFile: Non-allowed file {}'.format(filename)
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                elif type(text) is not str:
                    errStr = "PutTextFile: Only text data allowed"
                    response = {'status': 400, 'error': errStr}
                    logging.log(logging.WARNING, errStr)
                else:
                    with open(filename, 'w+') as volFile:
                        volFile.write(text)
                    response = {'status': 200}
            elif cmd == 'dataLog':
                    filename = request['filename']
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
        # merge request into the response dictionary
        response.update(request)
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
            if fileDir is not None and fileDir != '' and os.path.isabs(fileDir):
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
