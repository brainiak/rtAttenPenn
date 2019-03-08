import os
import sys
import time
import json
import logging
import threading
import websocket
from rtfMRI.utils import DebugLevels
from webInterface.WebClientUtils import login, certFile


class EventNotifier:
    ''' A process that listens for TTL and Keyboard input and forwards them to
        the cloud service.
    '''
    serverAddr = None
    sessionCookie = None
    needLogin = True
    shouldExit = False
    wsConns = []
    # Synchronizing across threads
    threadLock = threading.Lock()

    @staticmethod
    def runNotifier(serverAddr, retryInterval=10, username=None, password=None):
        EventNotifier.serverAddr = serverAddr
        # go into loop trying to do webSocket connection periodically
        while not EventNotifier.shouldExit:
            try:
                if EventNotifier.needLogin or EventNotifier.sessionCookie is None:
                    EventNotifier.sessionCookie = login(serverAddr, username, password)
                wsAddr = os.path.join('wss://', serverAddr, 'wsEvents')
                logging.log(DebugLevels.L6, "Trying connection: %s", wsAddr)
                ws = websocket.WebSocketApp(wsAddr,
                                            on_open=EventNotifier.on_open,
                                            on_message=EventNotifier.on_message,
                                            on_close=EventNotifier.on_close,
                                            on_error=EventNotifier.on_error,
                                            cookie="login="+EventNotifier.sessionCookie)
                logging.log(DebugLevels.L1, "Connected to: %s", wsAddr)
                ws.run_forever(sslopt={"ca_certs": certFile})
            except Exception as err:
                logging.log(logging.INFO, "EventNotifier {}: {}".
                            format(type(err).__name__, str(err)))
                time.sleep(retryInterval)

    @staticmethod
    def on_message(client, message):
        try:
            request = json.loads(message)
            cmd = request['cmd']
            if cmd == 'ping':
                # TODO - calculate RTT
                logging.log(logging.INFO, 'Ping')
            elif cmd == 'error':
                errorCode = request['status']
                if errorCode == 401:
                    EventNotifier.needLogin = True
                    EventNotifier.sessionCookie = None
                errStr = 'Error {}: {}'.format(errorCode, request['error'])
                logging.log(logging.ERROR, errStr)
            else:
                errStr = 'OnMessage: Unrecognized command {}'.format(cmd)
                logging.log(logging.WARNING, errStr)
        except Exception as err:
            errStr = "EventNotifier: OnMessage Exception: {}: {}".format(cmd, err)
            logging.log(logging.WARNING, errStr)
            if cmd == 'error':
                sys.exit()
        return

    @staticmethod
    def on_open(client):
        logging.log(DebugLevels.L1, "EventNotifier websocket opened")
        EventNotifier.threadLock.acquire()
        try:
            EventNotifier.wsConns.append(client)
        finally:
            EventNotifier.threadLock.release()

    @staticmethod
    def on_close(client):
        logging.log(DebugLevels.L1, "EventNotifier websocket closed")
        EventNotifier.threadLock.acquire()
        try:
            if client in EventNotifier.wsConns:
                EventNotifier.wsConns.remove(client)
        finally:
            EventNotifier.threadLock.release()

    @staticmethod
    def on_error(client, error):
        if type(error) is KeyboardInterrupt:
            EventNotifier.shouldExit = True
        else:
            logging.log(logging.WARNING, "EventNotifier: on_error: : {} {}".
                        format(type(error), str(error)))

    @staticmethod
    def sendMessage(msg):
        EventNotifier.threadLock.acquire()
        try:
            for client in EventNotifier.wsConns:
                client.send(msg)
        finally:
            EventNotifier.threadLock.release()
