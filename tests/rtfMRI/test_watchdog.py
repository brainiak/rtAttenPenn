import pytest
import os
import time
import threading
from glob import iglob
from queue import Queue, Empty
from rtfMRI.fileWatcher import FileWatcher

testDir = '/tmp/watchdog'


def test_watchdog():
    if not os.path.exists(testDir):
        os.makedirs(testDir)

    # remove any existing testfiles
    for filename in iglob(testDir + "test*.watchdog"):
        # print("remove {}".format(filename))
        os.remove(filename)

    watchQ = Queue()
    foundQ = Queue()

    watch_thread = threading.Thread(name='watchThread', target=watchThread, args=(watchQ, foundQ,))
    watch_thread.setDaemon(True)
    watch_thread.start()

    # create the new files
    for i in range(5):
        filename = os.path.join(testDir, "test{}.watchdog".format(i))
        watchQ.put(filename)
        time.sleep(0.25)
        # print('writing file {}'.format(filename))
        with open(filename, "w") as f:
            f.write("hello {}".format(i))
        foundFile = foundQ.get(block=True, timeout=0.5)
        # print('found file {}'.format(filename))
        assert foundFile == filename
        # assert re.match(foundFile, filename)

    watchQ.put('end')
    watch_thread.join(timeout=1)


def watchThread(watchQ, foundQ):
    fileWatcher = FileWatcher()
    fileWatcher.initFileNotifier(testDir, "*.watchdog", 1)

    req = watchQ.get()
    while req != 'end':
        filename = fileWatcher.waitForFile(req)
        foundQ.put(filename)
        req = watchQ.get()
