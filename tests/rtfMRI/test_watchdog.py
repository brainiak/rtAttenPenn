import pytest
import os
import time
import re
from queue import Queue, Empty
from glob import iglob
from watchdog.observers import Observer
from rtfMRI.fileWatcher import FileNotifyHandler

testDir = '/tmp/'


def test_watchdog():
    observer = Observer()
    eventQueue = Queue()
    fileHandler = FileNotifyHandler(eventQueue, ["*.watchdog"])
    observer.schedule(fileHandler, testDir, recursive=False)
    observer.start()

    # remove any existing testfiles
    for filename in iglob(testDir + "test*.watchdog"):
        # print("remove {}".format(filename))
        os.remove(filename)

    # create the new files
    for i in range(5):
        filename = testDir + "test{}.watchdog".format(i)
        # print("create {}".format(filename))
        with open(filename, "w") as f:
            f.write("hello {}".format(i))
        time.sleep(0.25)  # without sleep the events can get out of order

    # check that we got an event for each file
    print("get events")
    for i in range(5):
        filename = testDir + "test{}.watchdog".format(i)
        try:
            event, ts = eventQueue.get(block=True, timeout=0.5)
        except Empty as err:
            assert False  # we don't expect an empty queue
        # print("received event for {}, {}".format(event.src_path, event.event_type))
        assert re.match(filename, event.src_path)

    assert eventQueue.empty()
    observer.stop()
