import tornado.web
import tornado.websocket
import os
import time
import ssl
import json
import asyncio
import threading
import logging
from pathlib import Path
from base64 import b64decode
import rtfMRI.utils as utils
from rtfMRI.StructDict import StructDict
from rtfMRI.ReadDicom import readDicomFromBuffer
from rtfMRI.Messaging import getCertPath, getKeyPath
from rtfMRI.utils import DebugLevels
from rtfMRI.Errors import RequestError


certsDir = 'certs'
sslCertFile = 'rtAtten.crt'
sslPrivateKey = 'rtAtten_private.key'
# sslCertFile = 'bids_princeton_edu.crt'
# sslPrivateKey = 'bids_private.key'


def defaultCallback(client, message):
    print("client({}): msg({})".format(client, message))


class Web():
    ''' Cloud service web-interface that is the front-end to the data processing. '''
    app = None
    httpServer = None
    outputDir = ''
    # Arrays of WebSocket connections that have been established from client windows
    wsSubjConns = []  # type: ignore
    wsUserConns = []  # type: ignore
    wsDataConns = []  # type: ignore
    # Callback functions to invoke when message received from client window connection
    userWidnowCallback = defaultCallback
    subjWindowCallback = defaultCallback
    # Main html page to load
    webIndexPage = 'index.html'
    # Synchronizing data request events
    dataCallbacks = {}
    dataSequenceNum = 0
    dataLock = threading.Lock()

    @staticmethod
    def start(index='index.html', userCallback=defaultCallback,
              subjCallback=defaultCallback, port=8888):
        if Web.app is not None:
            raise RuntimeError("Web Interface already running.")
        Web.webIndexPage = index
        Web.subjWindowCallback = subjCallback
        Web.userWidnowCallback = userCallback
        webDir = Path(os.path.dirname(index)).parent
        src_root = os.path.join(webDir, 'src')
        css_root = os.path.join(webDir, 'css')
        img_root = os.path.join(webDir, 'img')
        build_root = os.path.join(webDir, 'build')
        Web.app = tornado.web.Application([
            (r'/', Web.UserHttp),
            (r'/wsUser', Web.UserWebSocket),
            (r'/wsSubject', Web.SubjectWebSocket),
            (r'/wsData', Web.DataWebSocket),
            (r'/src/(.*)', tornado.web.StaticFileHandler, {'path': src_root}),
            (r'/css/(.*)', tornado.web.StaticFileHandler, {'path': css_root}),
            (r'/img/(.*)', tornado.web.StaticFileHandler, {'path': img_root}),
            (r'/build/(.*)', tornado.web.StaticFileHandler, {'path': build_root}),
        ])
        # start event loop if needed
        try:
            asyncio.get_event_loop()
        except RuntimeError as err:
            # RuntimeError thrown if no current event loop
            # Start the event loop
            asyncio.set_event_loop(asyncio.new_event_loop())

        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_ctx.load_cert_chain(getCertPath(certsDir, sslCertFile),
                                getKeyPath(certsDir, sslPrivateKey))
        print("Listening on: http://localhost:{}".format(port))
        Web.httpServer = tornado.httpserver.HTTPServer(Web.app, ssl_options=ssl_ctx)
        Web.httpServer.listen(port)
        tornado.ioloop.IOLoop.current().start()

    @staticmethod
    def close():
        # Currently this should never be called
        assert False
        # for client in Web.wsUserConns[:]:
        #     client.close()
        # Web.wsUserConns = []
        # for client in Web.wsDataConns[:]:
        #     client.close()
        # Web.wsDataConns = []
        # for client in Web.wsSubjConns[:]:
        #     client.close()
        # Web.wsSubjConns = []
        pass

    @staticmethod
    def formatFileData(filename, data):
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

    @staticmethod
    def getFile(filename, asRawBytes=False):
        cmd = {'cmd': 'getFile', 'filename': filename}
        try:
            replyData = Web.sendDataMessage(cmd, timeout=5)
        except Exception as err:
            return None, err
        if asRawBytes is True:
            return replyData, None
        return Web.formatFileData(filename, replyData), None

    @staticmethod
    def getNewestFile(filename, asRawBytes=False):
        cmd = {'cmd': 'getNewestFile', 'filename': filename}
        try:
            replyData = Web.sendDataMessage(cmd, timeout=5)
        except Exception as err:
            return None, err
        if asRawBytes is True:
            return replyData, None
        return Web.formatFileData(filename, replyData), None

    @staticmethod
    def watchFile(filename,  asRawBytes=False, timeout=10):
        cmd = {'cmd': 'watchFile', 'filename': filename, 'timeout': timeout}
        # Note: sendDataMessage waits for reply and returns data received
        try:
            replyData = Web.sendDataMessage(cmd, timeout=timeout+5)
        except Exception as err:
            return None, err
        if asRawBytes is True:
            return replyData, None
        return Web.formatFileData(filename, replyData), None

    @staticmethod
    def initWatch(dir, filePattern, minFileSize):
        cmd = {
            'cmd': 'initWatch',
            'dir': dir,
            'filePattern': filePattern,
            'minFileSize': minFileSize
        }
        Web.sendDataMessage(cmd, timeout=30)

    @staticmethod
    def putTextFile(filename, str):
        cmd = {
            'cmd': 'putTextFile',
            'filename': filename,
            'data': str,
        }
        try:
            Web.sendDataMessage(cmd, timeout=5)
        except Exception as err:
            logging.warn('Web: putTextFile: error {}'.format(err))
            return False
        return True

    @staticmethod
    def dataLog(filename, logStr):
        cmd = {
            'cmd': 'dataLog',
            'logLine': logStr,
            'filename': filename,
        }
        try:
            Web.sendDataMessage(cmd, timeout=5)
        except Exception as err:
            logging.warn('Web: dataLog: error {}'.format(err))
            return False
        return True

    @staticmethod
    def userLog(logStr):
        cmd = {'cmd': 'userLog', 'value': logStr}
        Web.sendUserMessage(json.dumps(cmd))

    @staticmethod
    def setUserError(errStr):
        response = {'cmd': 'error', 'error': errStr}
        Web.sendUserMessage(json.dumps(response))

    @staticmethod
    def sendUserConfig(config):
        response = {'cmd': 'config', 'value': config}
        Web.sendUserMessage(json.dumps(response))

    @staticmethod
    def sendDataMessage(cmd, timeout=None):
        Web.dataLock.acquire()

        if len(Web.wsDataConns) == 0:
            Web.dataLock.release()
            raise RequestError("WebInterface: No Data Websocket Connection")
        if len(Web.wsDataConns) > 1:
            Web.dataLock.release()
            raise RequestError("WebInterface: Multiple Data Websocket Connections")

        try:
            Web.dataSequenceNum += 1
            seqNum = Web.dataSequenceNum
            cmd['seqNum'] = seqNum
            msg = json.dumps(cmd)

            callbackStruct = StructDict()
            callbackStruct.seqNum = seqNum
            callbackStruct.timeStamp = time.time()
            callbackStruct.event = threading.Event()
            callbackStruct.status = 0
            callbackStruct.error = None
            callbackStruct.fileData = b''
            Web.dataCallbacks[seqNum] = callbackStruct
            Web.wsDataConns[0].write_message(msg)
        except Exception as err:
            raise err
        finally:
            Web.dataLock.release()

        callbackStruct.event.wait(timeout)
        # TODO handle case where WS connection is broken
        if callbackStruct.event.is_set() is False:
            raise TimeoutError("Websocket: Data Request Timed Out({}) {}".format(timeout, msg))
        if callbackStruct.status != 200 or callbackStruct.error is not None:
            raise RequestError("WebInterface: Data Message: {}".format(callbackStruct.error))
        return callbackStruct.fileData

    @staticmethod
    def dataCallback(client, message):
        response = json.loads(message)
        seqNum = response['seqNum']
        origCmd = response['cmd']
        logging.log(DebugLevels.L6, "callback {}: {} {}".format(seqNum, origCmd, response['status']))
        # Thread Synchronized Section
        Web.dataLock.acquire()
        try:
            callbackStruct = Web.dataCallbacks.pop(seqNum, None)
            if callbackStruct is None:
                logging.error('WebServer: dataCallback seqNum {} not found, current seqNum {}'
                              .format(seqNum, Web.dataSequenceNum))
                return
            assert callbackStruct.seqNum == seqNum
            callbackStruct.status = response['status']
            if callbackStruct.status == 200:
                if origCmd in ('ping', 'initWatch', 'putTextFile', 'dataLog'):
                    pass
                elif origCmd in ('getFile', 'getNewestFile', 'watchFile'):
                    assert 'data' in response
                    callbackStruct.fileData = b64decode(response['data'])
                else:
                    callbackStruct.error = 'Unrecognized origCmd {}'.format(origCmd)
            else:
                assert 'error' in response and response['error'] != ''
                callbackStruct.error = response['error']
            callbackStruct.event.set()
        except Exception as err:
            logging.error('WebServer: dataCallback error: {}'.format(err))
        finally:
            Web.dataLock.release()
        Web.pruneCallbacks()

    @staticmethod
    def pruneCallbacks():
        numWaitingCallbacks = len(Web.dataCallbacks)
        if numWaitingCallbacks == 0:
            return
        logging.info('Web pruneCallbacks: checking {} callbaks'.format(numWaitingCallbacks))
        Web.dataLock.acquire()
        try:
            maxSeconds = 300
            now = time.time()
            for seqNum in Web.dataCallbacks.keys():
                # check how many seconds old each callback is
                cb = Web.dataCallbacks[seqNum]
                secondsElapsed = now - cb.timeStamp
                if secondsElapsed > maxSeconds:
                    # older than max threshold so remove
                    cb.status = 400
                    cb.error = 'Callback time exceeded max threshold {}s {}s'.format(maxSeconds, secondsElapsed)
                    cb.event.set()
                    del Web.dataCallbacks[seqNum]
        except Exception as err:
            logging.error('Web pruneCallbacks: error {}'.format(err))
        finally:
            Web.dataLock.release()

    @staticmethod
    def sendUserMessage(msg):
        for client in Web.wsUserConns:
            client.write_message(msg)

    class UserHttp(tornado.web.RequestHandler):
        def get(self):
            full_path = os.path.join(os.getcwd(), Web.webIndexPage)
            logging.log(DebugLevels.L6, 'Index request: pwd: {}'.format(full_path))
            self.render(full_path)

    class SubjectWebSocket(tornado.websocket.WebSocketHandler):
        def open(self):
            logging.log(DebugLevels.L1, "Subject WebSocket opened")
            Web.wsSubjConns.append(self)

        def on_close(self):
            logging.log(DebugLevels.L1, "Subject WebSocket closed")
            Web.wsSubjConns.remove(self)

        def on_message(self, message):
            Web.subjWindowCallback(self, message)

    class UserWebSocket(tornado.websocket.WebSocketHandler):
        def open(self):
            logging.log(DebugLevels.L1, "User WebSocket opened")
            Web.wsUserConns.append(self)

        def on_close(self):
            logging.log(DebugLevels.L1, "User WebSocket closed")
            Web.wsUserConns.remove(self)

        def on_message(self, message):
            Web.userWidnowCallback(self, message)

    class DataWebSocket(tornado.websocket.WebSocketHandler):
        def open(self):
            Web.dataLock.acquire()
            try:
                # Restrict to only one Data Connection at a time
                # close any existing connections
                for client in Web.wsDataConns[:]:
                    Web.wsDataConns.remove(client)
                    client.close()
                # add new connection
                logging.log(DebugLevels.L1, "Data WebSocket opened")
                Web.wsDataConns.append(self)
            except Exception as err:
                logging.error('WebServer: Open Data Socket error: {}'.format(err))
            finally:
                Web.dataLock.release()

        def on_close(self):
            Web.dataLock.acquire()
            try:
                logging.log(DebugLevels.L1, "Data WebSocket closed")
                Web.wsDataConns.remove(self)
                # signal the close to anyone waiting for replies
                for seqNum, cb in Web.dataCallbacks.items():
                    cb.status = 499
                    cb.error = 'Client closed connection'
                    cb.event.set()
                Web.dataCallbacks = {}
            finally:
                Web.dataLock.release()

        def on_message(self, message):
            Web.dataCallback(self, message)
