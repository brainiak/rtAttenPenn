import tornado.web
import tornado.websocket
import os
import json
import asyncio
import threading
import logging
from pathlib import Path
from base64 import b64decode
from rtfMRI.utils import DebugLevels
from rtfMRI.Errors import RequestError


def defaultCallback(client, message):
    print("client({}): msg({})".format(client, message))


def fileDataCallback(client, message):
    response = json.loads(message)
    logging.log(DebugLevels.L6, "callback: {} {}".format(response['cmd'], response['status']))
    origCmd = response.get('cmd')
    Web.dataStatus = response.get('status')
    Web.dataError = response.get('error')
    Web.fileData = b''
    if origCmd == 'ping' and Web.dataStatus == 200:
        pass
    elif origCmd == 'init' and Web.dataStatus == 200:
        pass
    elif origCmd == 'get' and Web.dataStatus == 200:
        assert 'data' in response
        Web.fileData = b64decode(response['data'])
    Web.dataCallbackEvent.set()


class Web():
    ''' Cloud service web-interface that is the front-end to the data processing. '''
    app = None
    httpServer = None
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
        build_root = os.path.join(webDir, 'build')
        Web.app = tornado.web.Application([
            (r'/', Web.UserHttp),
            (r'/wsUser', Web.UserWebSocket),
            (r'/wsSubject', Web.SubjectWebSocket),
            (r'/wsData', Web.DataWebSocket),
            (r'/src/(.*)', tornado.web.StaticFileHandler, {'path': src_root}),
            (r'/css/(.*)', tornado.web.StaticFileHandler, {'path': css_root}),
            (r'/build/(.*)', tornado.web.StaticFileHandler, {'path': build_root}),
        ])
        # start event loop if needed
        try:
            asyncio.get_event_loop()
        except RuntimeError as err:
            # RuntimeError thrown if no current event loop
            # Start the event loop
            asyncio.set_event_loop(asyncio.new_event_loop())

        Web.httpServer = tornado.httpserver.HTTPServer(Web.app)
        Web.httpServer.listen(port)
        tornado.ioloop.IOLoop.current().start()

    def close():
        for client in Web.wsUserConns:
            client.close()
        for client in Web.wsDataConns:
            client.close()
        for client in Web.wsSubjConns:
            client.close()

    @staticmethod
    def sendUserMessage(msg):
        for client in Web.wsUserConns:
            client.write_message(msg)

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
        if Web.dataStatus != 200:
            raise RequestError("WebInterface: Data Message: {}".format(Web.dataError))
        return True

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
