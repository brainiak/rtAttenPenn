import tornado.web
import tornado.websocket
import os
import ssl
import json
import asyncio
import threading
import logging
from pathlib import Path
from base64 import b64decode
import rtfMRI.utils as utils
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


def fileDataCallback(client, message):
    response = json.loads(message)
    logging.log(DebugLevels.L6, "callback: {} {}".format(response['cmd'], response['status']))
    origCmd = response.get('cmd')
    Web.dataStatus = response.get('status')
    Web.dataError = response.get('error')
    Web.fileData = b''
    if Web.dataStatus == 200:
        if origCmd in ('ping', 'initWatch', 'putTextFile', 'dataLog'):
            pass
        elif origCmd in ('getFile', 'getNewestFile', 'watchFile'):
            assert 'data' in response
            Web.fileData = b64decode(response['data'])
        else:
            Web.dataError = 'Unrecognized origCmd {}'.format(origCmd)
    else:
        assert Web.dataError is not None and Web.dataError != ''
    Web.dataCallbackEvent.set()


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
    dataWindowCallback = fileDataCallback
    # Main html page to load
    webIndexPage = 'index.html'
    # Communicating Events
    dataCallbackEvent = threading.Event()
    dataStatus = 0
    dataError = None
    fileData = b''

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
        for client in Web.wsUserConns:
            client.close()
        for client in Web.wsDataConns:
            client.close()
        for client in Web.wsSubjConns:
            client.close()

    @staticmethod
    def formatFileData(filename, data):
        fileExtension = Path(filename).suffix
        if fileExtension == '.mat':
            # Matlab file format
            result = utils.loadMatFileFromBuffer(Web.fileData)
        elif fileExtension == '.dcm':
            # Dicom file format
            result = readDicomFromBuffer(Web.fileData)
        else:
            result = Web.fileData
        return result

    @staticmethod
    def getFile(filename, asRawBytes=False):
        cmd = {'cmd': 'getFile', 'filename': filename}
        try:
            Web.sendDataMessage(json.dumps(cmd), timeout=5)
        except Exception as err:
            # TODO set web interface error
            return None, err
        if asRawBytes is True:
            return Web.fileData, None
        return Web.formatFileData(filename, Web.fileData), None

    @staticmethod
    def getNewestFile(filename, asRawBytes=False):
        cmd = {'cmd': 'getNewestFile', 'filename': filename}
        try:
            Web.sendDataMessage(json.dumps(cmd), timeout=5)
        except Exception as err:
            # TODO set web interface error
            return None, err
        if asRawBytes is True:
            return Web.fileData, None
        return Web.formatFileData(filename, Web.fileData), None

    @staticmethod
    def watchFile(filename,  asRawBytes=False, timeout=5):
        cmd = {'cmd': 'watchFile', 'filename': filename, 'timeout': timeout}
        # Note: sendDataMessage waits for reply and sets results in Web.fileData
        try:
            Web.sendDataMessage(json.dumps(cmd), timeout)
        except Exception as err:
            # TODO set web interface error
            return None, err
        if asRawBytes is True:
            return Web.fileData, None
        return Web.formatFileData(filename, Web.fileData), None

    @staticmethod
    def initWatch(dir, filePattern, minFileSize):
        cmd = {
            'cmd': 'initWatch',
            'dir': dir,
            'filePattern': filePattern,
            'minFileSize': minFileSize
        }
        Web.sendDataMessage(json.dumps(cmd), timeout=30)

    @staticmethod
    def putTextFile(filename, str):
        cmd = {
            'cmd': 'putTextFile',
            'filename': filename,
            'data': str,
        }
        Web.sendDataMessage(json.dumps(cmd), timeout=5)

    @staticmethod
    def dataLog(filename, logStr):
        cmd = {
            'cmd': 'dataLog',
            'logLine': logStr,
            'filename': filename,
        }
        Web.sendDataMessage(json.dumps(cmd), timeout=5)

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
    def sendDataMessage(msg, timeout=None):
        Web.dataStatus = 0
        Web.dataError = None
        Web.dataCallbackEvent.clear()
        for client in Web.wsDataConns:
            # TODO only allow one client?
            client.write_message(msg)
        Web.dataCallbackEvent.wait(timeout)
        # TODO handle case where WS connection is broken
        if Web.dataCallbackEvent.is_set() is False:
            raise TimeoutError("Websocket: Data Request Timed Out(%d) %s", timeout, msg)
        if Web.dataStatus != 200 or Web.dataError is not None:
            raise RequestError("WebInterface: Data Message: {}".format(Web.dataError))
        return True

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
            logging.log(DebugLevels.L1, "Data WebSocket opened")
            Web.wsDataConns.append(self)

        def on_close(self):
            logging.log(DebugLevels.L1, "Data WebSocket closed")
            Web.wsDataConns.remove(self)
            # signal the close to anyone listening
            Web.dataStatus = 499
            Web.dataError = 'Client closed connection'
            Web.fileData = b''
            Web.dataCallbackEvent.set()

        def on_message(self, message):
            Web.dataWindowCallback(self, message)
