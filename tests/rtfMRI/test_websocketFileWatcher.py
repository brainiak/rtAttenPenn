import pytest
import os
import threading
import time
import json
from rtfMRI.fileWatcher import WebSocketFileWatcher
from rtfMRI.WebInterface import Web


@pytest.fixture(scope="module")
def dicomTestFilename():  # type: ignore
    return os.path.join(os.path.dirname(__file__), 'test_input/001_000001_000001.dcm')


class TestDeadlines:
    webThread = None
    fileThread = None
    pingCount = 0

    def setup_class(cls):
        # Start a webInterface thread running
        webKwArgs = {'index': 'rtAtten/html/index.html', 'port': 8921}
        cls.webThread = threading.Thread(name='webThread', target=Web.start, kwargs=webKwArgs)
        cls.webThread.setDaemon(True)
        cls.webThread.start()

        # Start a fileWatcher thread running
        cls.fileThread = threading.Thread(
            name='fileThread',
            target=WebSocketFileWatcher.runFileWatcher,
            args=('localhost:8921',)
        )
        cls.fileThread.setDaemon(True)
        cls.fileThread.start()
        time.sleep(1)

    def teardown_class(cls):
        pass

    def test_ping(cls):
        global pingCallbackEvent
        # Send a ping request from webInterface to fileWatcher
        assert len(Web.wsDataConns) > 0
        cmd = {'cmd': 'ping'}
        msg = json.dumps(cmd)
        Web.sendDataMessage(msg, timeout=2)

    def test_getFile(cls, dicomTestFilename):
        global fileData
        assert len(Web.wsDataConns) > 0
        # initialize file watcher
        cmd = {'cmd': 'initWatch', 'dir': '/', 'filePattern': '*', 'minFileSize': 0}
        Web.sendDataMessage(json.dumps(cmd), timeout=1)
        with open(dicomTestFilename, 'rb') as fp:
            data = fp.read()
        cmd = {'cmd': 'watch', 'filename': dicomTestFilename}
        Web.sendDataMessage(json.dumps(cmd), timeout=2)
        assert data == Web.fileData
        cmd = {'cmd': 'get', 'filename': dicomTestFilename}
        Web.sendDataMessage(json.dumps(cmd), timeout=2)
        assert data == Web.fileData


    # TODO - test websocket connection closes

    # Get reply, write it to a file, diff the file with the original
