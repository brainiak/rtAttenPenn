import tornado.web
import tornado.websocket
import os
import time
import ssl
import json
import uuid
import bcrypt
import asyncio
import threading
import logging
from pathlib import Path
from base64 import b64decode
from rtfMRI.StructDict import StructDict
from rtfMRI.Messaging import getCertPath, getKeyPath
from rtfMRI.utils import DebugLevels, writeFile
from rtfMRI.Errors import StateError, RTError

certsDir = 'certs'
sslCertFile = 'rtAtten.crt'
sslPrivateKey = 'rtAtten_private.key'
CommonOutputDir = '/rtfmriData/'


def defaultCallback(client, message):
    print("client({}): msg({})".format(client, message))


class Web():
    ''' Cloud service web-interface that is the front-end to the data processing. '''
    app = None
    httpServer = None
    # Arrays of WebSocket connections that have been established from client windows
    wsSubjConns = []  # type: ignore
    wsUserConns = []  # type: ignore
    wsDataConn = None  # type: ignore  # Only one data connection
    # Callback functions to invoke when message received from client window connection
    userWidnowCallback = defaultCallback
    subjWindowCallback = defaultCallback
    # Main html page to load
    htmlDir = None
    webIndexPage = 'index.html'
    webLoginPage = 'login.html'
    dataCallbacks = {}
    dataSequenceNum = 0
    cbPruneTime = 0
    # Synchronizing across threads
    threadLock = threading.Lock()
    ioLoopInst = None
    test = False

    @staticmethod
    def start(htmlDir='html', userCallback=defaultCallback,
              subjCallback=defaultCallback, port=8888, test=False):
        if Web.app is not None:
            raise RuntimeError("Web Server already running.")
        Web.test = test
        Web.htmlDir = htmlDir
        Web.subjWindowCallback = subjCallback
        Web.userWidnowCallback = userCallback
        webDir = Path(htmlDir).parent
        src_root = os.path.join(webDir, 'src')
        css_root = os.path.join(webDir, 'css')
        img_root = os.path.join(webDir, 'img')
        build_root = os.path.join(webDir, 'build')
        cookieSecret = getCookieSecret(certsDir)
        settings = {
            "cookie_secret": cookieSecret,
            "login_url": "/login",
            "xsrf_cookies": True,
        }
        Web.app = tornado.web.Application([
            (r'/', Web.UserHttp),
            (r'/login', Web.LoginHandler),
            (r'/wsUser', Web.UserWebSocket),
            (r'/wsSubject', Web.SubjectWebSocket),
            (r'/wsData', Web.DataWebSocket),
            (r'/src/(.*)', tornado.web.StaticFileHandler, {'path': src_root}),
            (r'/css/(.*)', tornado.web.StaticFileHandler, {'path': css_root}),
            (r'/img/(.*)', tornado.web.StaticFileHandler, {'path': img_root}),
            (r'/build/(.*)', tornado.web.StaticFileHandler, {'path': build_root}),
        ], **settings)
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
        print("Listening on: https://localhost:{}".format(port))
        Web.httpServer = tornado.httpserver.HTTPServer(Web.app, ssl_options=ssl_ctx)
        Web.httpServer.listen(port)
        Web.ioLoopInst = tornado.ioloop.IOLoop.current()
        Web.ioLoopInst.start()

    @staticmethod
    def stop():
        Web.ioLoopInst.add_callback(Web.ioLoopInst.stop)
        Web.app = None

    @staticmethod
    def close():
        # Currently this should never be called
        raise StateError("Web close() called")

        Web.threadLock.acquire()
        try:
            if Web.wsDataConn is not None:
                Web.wsDataConn.close()
            Web.wsDataConn = None

            for client in Web.wsUserConns[:]:
                client.close()
            Web.wsUserConns = []

            for client in Web.wsSubjConns[:]:
                client.close()
            Web.wsSubjConns = []
        finally:
            Web.threadLock.release()

    @staticmethod
    def dataLog(filename, logStr):
        cmd = {'cmd': 'dataLog', 'logLine': logStr, 'filename': filename}
        try:
            Web.sendDataMsgFromThread(cmd, timeout=5)
        except Exception as err:
            logging.warn('Web: dataLog: error {}'.format(err))
            return False
        return True

    @staticmethod
    def userLog(logStr):
        cmd = {'cmd': 'userLog', 'value': logStr}
        Web.sendUserMsgFromThread(json.dumps(cmd))

    @staticmethod
    def setUserError(errStr):
        response = {'cmd': 'error', 'error': errStr}
        Web.sendUserMsgFromThread(json.dumps(response))

    @staticmethod
    def sendUserConfig(config, filesremote=True):
        response = {'cmd': 'config', 'value': config, 'filesremote': filesremote}
        Web.sendUserMsgFromThread(json.dumps(response))

    @staticmethod
    def sendDataMessage(cmd, callbackStruct):
        if callbackStruct is None or callbackStruct.event is None:
            raise StateError("sendDataMessage: No threading.event attribute in callbackStruct")
        Web.threadLock.acquire()
        try:
            Web.dataSequenceNum += 1
            seqNum = Web.dataSequenceNum
            cmd['seqNum'] = seqNum
            msg = json.dumps(cmd)
            callbackStruct.seqNum = seqNum
            callbackStruct.timeStamp = time.time()
            callbackStruct.status = 0
            callbackStruct.error = None
            Web.dataCallbacks[seqNum] = callbackStruct
            Web.wsDataConn.write_message(msg)
        except Exception as err:
            errStr = 'sendDataMessage error: type {}: {}'.format(type(err), str(err))
            raise RTError(errStr)
        finally:
            Web.threadLock.release()

    @staticmethod
    def dataCallback(client, message):
        response = json.loads(message)
        if 'cmd' not in response:
            raise StateError('dataCallback: cmd field missing from response: {}'.format(response))
        if 'status' not in response:
            raise StateError('dataCallback: status field missing from response: {}'.format(response))
        if 'seqNum' not in response:
            raise StateError('dataCallback: seqNum field missing from response: {}'.format(response))
        seqNum = response['seqNum']
        origCmd = response['cmd']
        logging.log(DebugLevels.L6, "callback {}: {} {}".format(seqNum, origCmd, response['status']))
        # Thread Synchronized Section
        Web.threadLock.acquire()
        try:
            callbackStruct = Web.dataCallbacks.pop(seqNum, None)
            if callbackStruct is None:
                logging.error('WebServer: dataCallback seqNum {} not found, current seqNum {}'
                              .format(seqNum, Web.dataSequenceNum))
                return
            if callbackStruct.seqNum != seqNum:
                # This should never happen
                raise StateError('seqNum mismtach {} {}'.format(callbackStruct.seqNum, seqNum))
            callbackStruct.response = response
            callbackStruct.status = response['status']
            if callbackStruct.status == 200:
                if origCmd in ('ping', 'initWatch', 'putTextFile', 'dataLog'):
                    pass
                elif origCmd in ('getFile', 'getNewestFile', 'watchFile'):
                    if 'data' not in response:
                        raise StateError('dataCallback: data field missing from response: {}'.format(response))
                else:
                    callbackStruct.error = 'Unrecognized origCmd {}'.format(origCmd)
            else:
                if 'error' not in response or response['error'] == '':
                    raise StateError('dataCallback: error field missing from response: {}'.format(response))
                callbackStruct.error = response['error']
            callbackStruct.event.set()
        except Exception as err:
            logging.error('WebServer: dataCallback error: {}'.format(err))
            raise err
        finally:
            Web.threadLock.release()
        if time.time() > Web.cbPruneTime:
            Web.cbPruneTime = time.time() + 60
            Web.pruneCallbacks()

    @staticmethod
    def pruneCallbacks():
        numWaitingCallbacks = len(Web.dataCallbacks)
        if numWaitingCallbacks == 0:
            return
        logging.info('Web pruneCallbacks: checking {} callbaks'.format(numWaitingCallbacks))
        Web.threadLock.acquire()
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
                    cb.response = {'cmd': 'unknown', 'status': cb.status, 'error': cb.error}
                    cb.event.set()
                    del Web.dataCallbacks[seqNum]
        except Exception as err:
            logging.error('Web pruneCallbacks: error {}'.format(err))
        finally:
            Web.threadLock.release()

    @staticmethod
    def sendUserMessage(msg):
        Web.threadLock.acquire()
        try:
            for client in Web.wsUserConns:
                client.write_message(msg)
        finally:
            Web.threadLock.release()

    @staticmethod
    def sendDataMsgFromThread(msg, timeout=None):
        if Web.wsDataConn is None:
            raise StateError("WebServer: No Data Websocket Connection")
        callbackStruct = StructDict()
        callbackStruct.event = threading.Event()
        # schedule the call with io thread
        Web.ioLoopInst.add_callback(Web.sendDataMessage, msg, callbackStruct)
        # wait for completion of call
        callbackStruct.event.wait(timeout)
        if callbackStruct.event.is_set() is False:
            raise TimeoutError("sendDataMessage: Data Request Timed Out({}) {}".format(timeout, msg))
        if callbackStruct.response is None:
            raise StateError('sendDataMessage: callbackStruct.response is None for command {}'.format(msg))
        if callbackStruct.status == 200 and 'writefile' in callbackStruct.response:
            writeResponseDataToFile(callbackStruct.response)
        return callbackStruct.response

    @staticmethod
    def sendUserMsgFromThread(msg):
        Web.ioLoopInst.add_callback(Web.sendUserMessage, msg)

    class UserHttp(tornado.web.RequestHandler):
        def get_current_user(self):
            return self.get_secure_cookie("login", max_age_days=0.2)

        @tornado.web.authenticated
        def get(self):
            full_path = os.path.join(Web.htmlDir, Web.webIndexPage)
            logging.log(DebugLevels.L6, 'Index request: pwd: {}'.format(full_path))
            Web.threadLock.acquire()
            try:
                self.render(full_path)
            finally:
                Web.threadLock.release()

    class LoginHandler(tornado.web.RequestHandler):
        error = ''

        def get(self):
            full_path = os.path.join(Web.htmlDir, Web.webLoginPage)
            self.render(full_path, error_msg=Web.LoginHandler.error)

        def post(self):
            # TODO - prevent more than 5 password attempts
            Web.LoginHandler.error = ''
            try:
                login_name = self.get_argument("name")
                login_passwd = self.get_argument("password")
                if Web.test is True:
                    if login_name == login_passwd == 'test':
                        self.set_secure_cookie("login", login_name, expires_days=0.2)
                        self.redirect("/")
                        return
                passwdFilename = os.path.join(certsDir, 'passwd')
                passwdDict = loadPasswdFile(passwdFilename)
                if login_name in passwdDict:
                    hashed_passwd = passwdDict[login_name]
                    # checkpw expects bytes array rather than string so use .encode()
                    if bcrypt.checkpw(login_passwd.encode(), hashed_passwd.encode()) is True:
                        self.set_secure_cookie("login", login_name, expires_days=0.2)
                        self.redirect("/")
                        return
                    else:
                        Web.LoginHandler.error = 'Login Error: Incorrect Password'
                else:
                    Web.LoginHandler.error = 'Login Error: Invalid Username'
            except Exception as err:
                Web.LoginHandler.error = str(err)
            self.redirect("/login")

    class SubjectWebSocket(tornado.websocket.WebSocketHandler):
        def open(self):
            user_id = self.get_secure_cookie("login")
            if not user_id:
                response = {'cmd': 'error', 'error': 'Websocket authentication failed'}
                self.write_message(json.dumps(response))
                self.close()
                return
            logging.log(DebugLevels.L1, "Subject WebSocket opened")
            Web.threadLock.acquire()
            try:
                Web.wsSubjConns.append(self)
            finally:
                Web.threadLock.release()

        def on_close(self):
            logging.log(DebugLevels.L1, "Subject WebSocket closed")
            Web.threadLock.acquire()
            try:
                if self in Web.wsSubjConns:
                    Web.wsSubjConns.remove(self)
            finally:
                Web.threadLock.release()

        def on_message(self, message):
            Web.subjWindowCallback(self, message)

    class UserWebSocket(tornado.websocket.WebSocketHandler):
        # def get(self, *args, **kwargs):
        #     if self.get_secure_cookie("login"):
        #         super(Web.SubjectWebSocket, self).get(*args, **kwargs)
        #     else:
        #         What to do here when authentication fails?
        #         return

        def open(self):
            user_id = self.get_secure_cookie("login")
            if not user_id:
                response = {'cmd': 'error', 'error': 'Websocket authentication failed'}
                self.write_message(json.dumps(response))
                self.close()
                return
            logging.log(DebugLevels.L1, "User WebSocket opened")
            Web.threadLock.acquire()
            try:
                Web.wsUserConns.append(self)
            finally:
                Web.threadLock.release()

        def on_close(self):
            logging.log(DebugLevels.L1, "User WebSocket closed")
            Web.threadLock.acquire()
            try:
                if self in Web.wsUserConns:
                    Web.wsUserConns.remove(self)
                else:
                    logging.log(DebugLevels.L1, "on_close: connection not in list")
            finally:
                Web.threadLock.release()

        def on_message(self, message):
            Web.userWidnowCallback(self, message)

    class DataWebSocket(tornado.websocket.WebSocketHandler):
        def open(self):
            user_id = self.get_secure_cookie("login")
            if not user_id:
                logging.warn('Data websocket authentication failed')
                response = {'cmd': 'error', 'status': 401, 'error': 'Websocket authentication failed'}
                self.write_message(json.dumps(response))
                self.close()
                return
            logging.log(DebugLevels.L1, "Data WebSocket opened")
            Web.threadLock.acquire()
            try:
                # close any existing connections
                if Web.wsDataConn is not None:
                    Web.wsDataConn.close()
                # add new connection
                Web.wsDataConn = self
            except Exception as err:
                logging.error('WebServer: Open Data Socket error: {}'.format(err))
            finally:
                Web.threadLock.release()

        def on_close(self):
            if Web.wsDataConn != self:
                logging.log(DebugLevels.L1, "on_close: Data Socket mismatch")
                return
            logging.log(DebugLevels.L1, "Data WebSocket closed")
            Web.threadLock.acquire()
            try:
                Web.wsDataConn = None
                # signal the close to anyone waiting for replies
                for seqNum, cb in Web.dataCallbacks.items():
                    cb.status = 499
                    cb.error = 'Client closed connection'
                    cb.response = {'cmd': 'unknown', 'status': cb.status, 'error': cb.error}
                    cb.event.set()
                Web.dataCallbacks = {}
            finally:
                Web.threadLock.release()

        def on_message(self, message):
            Web.dataCallback(self, message)


def loadPasswdFile(filename):
    with open(filename, 'r') as fh:
        entries = fh.readlines()
    passwdDict = {k: v for (k, v) in [line.strip().split(',') for line in entries]}
    return passwdDict


def storePasswdFile(filename, passwdDict):
    with open(filename, 'w') as fh:
        for k, v in passwdDict.items():
            fh.write('{},{}\n'.format(k, v))


def getCookieSecret(dir):
    filename = os.path.join(dir, 'cookie-secret')
    if os.path.exists(filename):
        with open(filename, mode='rb') as fh:
            cookieSecret = fh.read()
    else:
        cookieSecret = uuid.uuid4().bytes
        with open(filename, mode='wb') as fh:
            fh.write(cookieSecret)
    return cookieSecret


def makeFifo():
    fifodir = '/tmp/pipes/'
    if not os.path.exists(fifodir):
        os.makedirs(fifodir)
    # remove all previous pipes
    for p in Path(fifodir).glob("rtatten_*"):
        p.unlink()
    # create new pipe
    fifoname = os.path.join(fifodir, 'rtatten_pipe_{}'.format(int(time.time())))
    # fifo stuct
    webpipes = StructDict()
    webpipes.name_out = fifoname + '.toclient'
    webpipes.name_in = fifoname + '.fromclient'
    if not os.path.exists(webpipes.name_out):
        os.mkfifo(webpipes.name_out)
    if not os.path.exists(webpipes.name_in):
        os.mkfifo(webpipes.name_in)
    webpipes.fifoname = fifoname
    return webpipes


def handleFifoRequests(webServer, webpipes):
    '''A thread routine that listens for web requests through a pair of named pipes.
    This allows another process to send web requests without directly integrating
    the web server into the process.
    Listens on an fd_in pipe for requests and writes the results back on the fd_out pipe.
    '''
    global CommonOutputDir
    webpipes.fd_out = open(webpipes.name_out, mode='w', buffering=1)
    webpipes.fd_in = open(webpipes.name_in, mode='r')
    try:
        while True:
            msg = webpipes.fd_in.readline()
            if len(msg) == 0:
                # fifo closed
                break
            # parse command
            cmd = json.loads(msg)
            if 'cmd' not in cmd:
                raise StateError('handleFifoRequests: cmd field not in command: {}'.format(cmd))
            reqType = cmd['cmd']
            response = StructDict({'status': 200})
            if reqType == 'webCommonDir':
                response.filename = CommonOutputDir
            else:
                try:
                    response = webServer.sendDataMsgFromThread(cmd, timeout=10)
                    if response is None:
                        raise StateError('handleFifoRequests: Response None from sendDataMessage')
                    if 'status' not in response:
                        raise StateError('handleFifoRequests: status field missing from response: {}'.format(response))
                    if response['status'] not in (200, 408):
                        if 'error' not in response:
                            raise StateError('handleFifoRequests: error field missing from response: {}'.format(response))
                        webServer.setUserError(response['error'])
                        logging.error('handleFifo status {}: {}'.format(response['status'], response['error']))
                except Exception as err:
                    errStr = 'SendDataMessage Exception type {}: error {}:'.format(type(err), str(err))
                    response = {'status': 400, 'error': errStr}
                    webServer.setUserError(errStr)
                    logging.error('handleFifo Excpetion: {}'.format(errStr))
                    raise err
            try:
                webpipes.fd_out.write(json.dumps(response) + os.linesep)
            except BrokenPipeError:
                print('handleFifoRequests: pipe broken')
                break
        # End while loop
    finally:
        logging.info('handleFifo thread exit')
        webpipes.fd_in.close()
        webpipes.fd_out.close()


def resignalFifoThreadExit(fifoThread, webpipes):
    '''Under normal exit conditions the fifothread will exit when the fifo filehandles
    are closed. However if the fifo filehandles were never opened by both ends then
    the fifothread can be blocked waiting for them to open. To handle that case
    we open both filehandles with O_NONBLOCK flag so that if the fifo thread reader
    is listening it will be opened and closed, if not it will throw OSError exception
    in which case the fifothread has already exited and closed the fifo filehandles.
    '''
    if fifoThread is None:
        return
    try:
        pipeout = os.open(webpipes.name_out, os.O_RDONLY | os.O_NONBLOCK)
        os.close(pipeout)
        pipein = os.open(webpipes.name_in, os.O_WRONLY | os.O_NONBLOCK)
        os.close(pipein)
    except OSError as err:
        # No reader/writer listening on file so fifoThread already exited
        pass
    fifoThread.join(timeout=1)
    if fifoThread.is_alive() is not False:
        raise StateError('runSession: fifoThread not completed')


def writeResponseDataToFile(response):
    '''For responses that have writefile set, write the data to a file'''
    global CommonOutputDir
    if response['status'] != 200:
        raise StateError('writeResponseDataToFile: status not 200')
    if 'writefile' in response and response['writefile'] is True:
        # write the returned data out to a file
        if 'data' not in response:
            raise StateError('writeResponseDataToFile: data field not in response: {}'.format(response))
        if 'filename' not in response:
            del response['data']
            raise StateError('writeResponseDataToFile: filename field not in response: {}'.format(response))
        filename = response['filename']
        decodedData = b64decode(response['data'])
        # prepend with common output path and write out file
        # note: can't just use os.path.join() because if two or more elements
        #   have an aboslute path it discards the earlier elements
        outputFilename = os.path.normpath(CommonOutputDir + filename)
        dirName = os.path.dirname(outputFilename)
        if not os.path.exists(dirName):
            os.makedirs(dirName)
        writeFile(outputFilename, decodedData)
        response['filename'] = outputFilename
        del response['data']
