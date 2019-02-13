import pytest
import os
import threading
import time
import logging
from base64 import b64decode
from rtfMRI.utils import installLoggers
from webInterface.webSocketFileWatcher import WebSocketFileWatcher
from webInterface.WebServer import Web
import webInterface.WebClientUtils as wcutils


testDir = os.path.dirname(__file__)


@pytest.fixture(scope="module")
def dicomTestFilename():  # type: ignore
    return os.path.join(testDir, 'test_input/001_000001_000001.dcm')


class TestFileWatcher:
    webThread = None
    fileThread = None
    pingCount = 0

    def setup_class(cls):
        installLoggers(logging.DEBUG, logging.DEBUG, filename='logs/tests.log')
        # Start a webServer thread running
        webKwArgs = {'index': 'rtAtten/html/index.html', 'port': 8921}
        cls.webThread = threading.Thread(name='webThread', target=Web.start, kwargs=webKwArgs)
        cls.webThread.setDaemon(True)
        cls.webThread.start()
        time.sleep(1)

        # Start a fileWatcher thread running
        cls.fileThread = threading.Thread(
            name='fileThread',
            target=WebSocketFileWatcher.runFileWatcher,
            args=('localhost:8921',),
            kwargs={'retryInterval': 0.5, 'allowedDirs':['/tmp', testDir], 'allowedTypes':['.dcm', '.mat']}
        )
        cls.fileThread.setDaemon(True)
        cls.fileThread.start()
        time.sleep(1)

    def teardown_class(cls):
        Web.stop()
        time.sleep(1)
        pass

    def test_ping(cls):
        print("test_ping")
        global pingCallbackEvent
        # Send a ping request from webServer to fileWatcher
        assert Web.wsDataConn is not None
        cmd = {'cmd': 'ping'}
        Web.sendDataMsgFromThread(cmd, timeout=2)

    def test_validateRequestedFile(cls):
        print("test_validateRequestedFile")
        res = WebSocketFileWatcher.validateRequestedFile('/tmp/data', None)
        assert res is True

        res = WebSocketFileWatcher.validateRequestedFile('/tmp/data', 'file.dcm')
        assert res is True

        res = WebSocketFileWatcher.validateRequestedFile('/tmp/data', 'file.not')
        assert res is False

        res = WebSocketFileWatcher.validateRequestedFile('/sys/data', 'file.dcm')
        assert res is False

        res = WebSocketFileWatcher.validateRequestedFile(None, '/tmp/data/file.dcm')
        assert res is True

        res = WebSocketFileWatcher.validateRequestedFile(None, '/sys/data/file.dcm')
        assert res is False


    def test_getFile(cls, dicomTestFilename):
        print("test_getFile")
        global fileData
        assert Web.wsDataConn is not None
        # Try to initialize file watcher with non-allowed directory
        cmd = wcutils.initWatchReqStruct('/', '*', 0)
        response = Web.sendDataMsgFromThread(cmd)
        # we expect an error because '/' directory not allowed
        assert response['status'] == 400

        # Initialize with allowed directory
        cmd = wcutils.initWatchReqStruct(testDir, '*', 0)
        response = Web.sendDataMsgFromThread(cmd)
        assert response['status'] == 200

        with open(dicomTestFilename, 'rb') as fp:
            data = fp.read()

        cmd = wcutils.watchFileReqStruct(dicomTestFilename)
        response = Web.sendDataMsgFromThread(cmd)
        assert response['status'] == 200
        responseData = b64decode(response['data'])
        assert responseData == data

        cmd = wcutils.getFileReqStruct(dicomTestFilename)
        response = Web.sendDataMsgFromThread(cmd)
        assert response['status'] == 200
        responseData = b64decode(response['data'])
        assert responseData == data

        cmd = wcutils.getNewestFileReqStruct(dicomTestFilename)
        response = Web.sendDataMsgFromThread(cmd)
        assert response['status'] == 200
        responseData = b64decode(response['data'])
        assert responseData == data

        # Try to get a non-allowed file
        cmd = wcutils.getFileReqStruct('/tmp/file.nope')
        response = Web.sendDataMsgFromThread(cmd)
        assert(response['status'] == 400)

        # try from a non-allowed directory
        cmd = wcutils.getFileReqStruct('/nope/file.dcm')
        response = Web.sendDataMsgFromThread(cmd)
        assert(response['status'] == 400)
