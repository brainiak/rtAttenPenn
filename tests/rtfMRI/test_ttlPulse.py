import pytest
import os
import sys
import time
import subprocess
currPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.join(currPath, "../../")
sys.path.append(rootPath)
import rtfMRI.ttlPulse as ttl


class TestDeadlines:
    serverProc = None

    def setup_class(cls):
        # Start Pulse Server
        cls.serverProc = subprocess.Popen(['python', 'rtfMRI/ttlPulse.py'])
        # Start Pulse Client
        cls.pulseClient = ttl.TTLPulseClient()

    def teardown_class(cls):
        print("Stop pulseClient")
        cls.pulseClient.close()
        print("Stop pulseServer")
        cls.serverProc.kill()

    def test_receivePulse(self):
        pulseEvent = self.pulseClient.getPulseEvent()
        loopCount = 5
        pulseCount = 0
        for i in range(loopCount):
            recvPulse = pulseEvent.wait(2)
            if recvPulse:
                ts = self.pulseClient.getTimestamp()
                print("Client received {}".format(ts))
                pulseCount += 1
        assert pulseCount == loopCount

    # TODO - get this test working
    # def test_timestampResets(self):
    #     self.pulseClient.setMaxTRTime(.2)
    #     pulseEvent = self.pulseClient.getPulseEvent()
    #     loopCount = 5
    #     pulseCount = 0
    #     for i in range(loopCount):
    #         recvPulse = pulseEvent.wait(2)
    #         if i < 3:
    #             continue
    #         if recvPulse:
    #             if self.pulseClient.getTimestamp() != 0:
    #                 # timestamp should reset at 1.5 * maxTR or every .3 seconds
    #                 time.sleep(.3)
    #             # pulse should be reset now
    #             assert self.pulseClient.getTimestamp() == 0
    #             print("Client received timestamp 0")
    #             pulseCount += 1
    #     assert pulseCount == loopCount
