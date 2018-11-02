import os
import time
import json
import logging
import websocket
from base64 import b64encode
from queue import Queue, Empty
from watchdog.events import PatternMatchingEventHandler  # type: ignore
from watchdog.observers import Observer  # type: ignore
from rtfMRI.utils import DebugLevels


class FileWatcher():
    def __init__(self):
        self.observer = None
        self.fileNotifyHandler = None
        self.fileNotifyQ = Queue()  # type: None
        self.filePattern = None
        self.dir = None
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
        self.dir = dir
        self.fileNotifyHandler = FileNotifyHandler(self.fileNotifyQ, [filePattern])
        self.observer.schedule(self.fileNotifyHandler, dir, recursive=False)
        self.observer.start()

    def waitForFile(self, specificFileName, timeout=0):
        fileExists = os.path.exists(specificFileName)
        if not fileExists:
            if self.observer is None:
                raise FileNotFoundError("No fileNotifier and dicom file not found %s" % (specificFileName))
            else:
                logging.log(DebugLevels.L6, "Waiting for file: %s", specificFileName)
        eventLoopCount = 0
        exitWithFileEvent = False
        startTime = time.time()
        timeToCheckForFile = time.time() + 1  # check if file exists at least every second
        while not fileExists:
            if timeout > 0 and startTime + timeout > time.time():
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
                    "fileEventCaptured %s, fileName %s",
                    eventLoopCount, totalWriteWait,
                    exitWithFileEvent, specificFileName)
        return specificFileName


class FileNotifyHandler(PatternMatchingEventHandler):  # type: ignore
    def __init__(self, q, patterns):
        super().__init__(patterns=patterns)
        self.q = q

    def on_created(self, event):
        self.q.put((event, time.time()))

    def on_modified(self, event):
        self.q.put((event, time.time()))


class WebSocketFileWatcher:
    ''' A server that watches for files on the scanner computer and replies to
        cloud service requests with the file data.
    '''
    fileWatcher = FileWatcher()

    @staticmethod
    def runFileWatcher(serverAddr, retryInterval=10):
        # go into loop trying to do webSocket connection periodically
        while True:
            try:
                wsAddr = os.path.join('ws://', serverAddr, 'wsData')
                logging.log(DebugLevels.L6, "Trying connection: %s", wsAddr)
                ws = websocket.WebSocketApp(wsAddr,
                                            on_message=WebSocketFileWatcher.on_message,
                                            on_error=WebSocketFileWatcher.on_error)
                logging.log(DebugLevels.L1, "Connected to: %s", wsAddr)
                ws.run_forever()
            except Exception as err:
                logging.log(logging.INFO, "WSFileWatcher Exception: %s", str(err))
            time.sleep(retryInterval)

    def on_message(client, message):
        fileWatcher = WebSocketFileWatcher.fileWatcher
        request = json.loads(message)
        cmd = request['cmd']
        if cmd == "initWatch":
            dir = request['dir']
            filePattern = request['filePattern']
            minFileSize = request['minFileSize']
            logging.log(DebugLevels.L3, "init: %s, %s, %d", dir, filePattern, minFileSize)
            if dir is None or filePattern is None or minFileSize is None:
                response = {'status': 400, 'error': 'missing file information'}
            else:
                fileWatcher.initFileNotifier(dir, filePattern, minFileSize)
                response = {'status': 200}
        elif cmd == "watch":
            filename = request['filename']
            logging.log(DebugLevels.L3, "watch: %s", filename)
            if filename is None:
                response = {'status': 400, 'error': 'missing filename'}
            elif fileWatcher.observer is None:
                # fileWatcher hasn't been initialized yet
                response = {'status': 400, 'error': 'fileWatcher not initialized'}
            else:
                fileWatcher.waitForFile(filename)
                with open(filename, 'rb') as fp:
                    data = fp.read()
                b64Data = b64encode(data)
                b64StrData = b64Data.decode('utf-8')
                response = {'status': 200, 'data': b64StrData}
        elif cmd == "get":
            filename = request['filename']
            logging.log(DebugLevels.L3, "get: %s", filename)
            if filename is None:
                response = {'status': 400, 'error': 'missing filename'}
            if not os.path.exists(filename):
                response = {'status': 400, 'error': 'file not found'}
            else:
                with open(filename, 'rb') as fp:
                    data = fp.read()
                b64Data = b64encode(data)
                b64StrData = b64Data.decode('utf-8')
                response = {'status': 200, 'data': b64StrData}
        elif cmd == "ping":
            response = {'status': 200}
        else:
            response = {'status': 400, 'error': 'Unrecognized command {}'.format(cmd)}
        # merge request into the response dictionary
        response.update(request)
        client.send(json.dumps(response))

    def on_error(client, error):
        logging.log(logging.WARNING, "on_error: WSFileWatcher: %s", error)
