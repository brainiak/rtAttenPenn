import pytest  # type: ignore
import os
import re
import time
import threading
import inspect
import typing
from ServerMain import ServerMain
from rtfMRI.RtfMRIClient import loadConfigFile
from rtfMRI.StructDict import copy_toplevel
from rtfMRI.ReadDicom import applyMask
from rtfMRI.MsgTypes import MsgEvent, MsgResult
from rtfMRI.Errors import RequestError
from rtAtten.RtAttenClient import RtAttenClient
from rtAtten.PatternsDesign2Config import createRunConfig, getLocalPatternsFile
import tests.rtfMRI.simfmri.generate_data as gd


cfgFile = './syntheticDataCfg.toml'


def getCfgFileFullPath():  # type: ignore
    """Get the directory of this test file"""
    frame = inspect.currentframe()
    moduleFile = typing.cast(str, frame.f_code.co_filename)  # type: ignore
    moduleDir = os.path.dirname(moduleFile)
    cfgFullPath = os.path.join(moduleDir, cfgFile)
    return cfgFullPath


class TestDeadlines:
    serverPort = 5212
    client = None
    server = None
    run = None
    block = None
    TR_id = 0

    def setup_class(cls):
        cfgFilePath = getCfgFileFullPath()
        print("## Init TestDeadlines ##")
        # generate data if needed
        print("## Generate Data if needed ##")
        gd.generate_data(cfgFilePath)

        # Start Server
        cls.server = threading.Thread(name='server', target=ServerMain, args=(cls.serverPort,))
        cls.server.setDaemon(True)
        cls.server.start()

        # Start client
        cls.cfg = loadConfigFile(cfgFilePath)
        cls.client = RtAttenClient()
        cls.client.connect('localhost', cls.serverPort)
        cls.client.initSession(cls.cfg)

        # Run Client Until first TR
        runId = cls.cfg.session.Runs[0]
        scanNum = cls.cfg.session.ScanNums[0]
        patterns = getLocalPatternsFile(cls.cfg.session, runId)
        run = createRunConfig(cls.cfg.session, patterns, runId, scanNum)
        cls.client.id_fields.runId = run.runId
        blockGroup = run.blockGroups[0]
        cls.client.id_fields.blkGrpId = blockGroup.blkGrpId
        block = blockGroup.blocks[0]
        cls.client.id_fields.blockId = block.blockId
        runCfg = copy_toplevel(run)
        reply = cls.client.sendCmdExpectSuccess(MsgEvent.StartRun, runCfg)
        blockGroupCfg = copy_toplevel(blockGroup)
        reply = cls.client.sendCmdExpectSuccess(MsgEvent.StartBlockGroup, blockGroupCfg)
        blockCfg = copy_toplevel(block)
        reply = cls.client.sendCmdExpectSuccess(MsgEvent.StartBlock, blockCfg)
        assert reply.result == MsgResult.Success
        cls.run = run
        cls.block = block

    def teardown_class(cls):
        print("## Stop TestDeadlines ##")
        print("client send shutdown to server")
        cls.client.sendShutdownServer()
        cls.server.join(timeout=2)
        assert cls.server.is_alive() is False

    def getNextTR(self):
        TR = self.block.TRs[self.TR_id]
        self.TR_id += 1
        self.client.id_fields.trId = TR.trId
        # Assuming the output file volumes are still 1's based
        fileNum = TR.vol + self.run.disdaqs // self.run.TRTime
        trVolumeData = self.client.getNextTRData(self.run, fileNum)
        TR.data = applyMask(trVolumeData, self.client.cfg.session.roiInds)
        return TR

    def getDeadline(self, secondstil):
        val = time.time() + self.client.cfg.clockSkew - (0.5 * self.client.cfg.maxRTT) + secondstil
        return val

    def test_noDeadline(self):
        print("## test_completeWithinDeadline ##")
        TR = self.getNextTR()
        if TR.deadline is not None:
            del TR['deadline']
        reply = self.client.sendCmdExpectSuccess(MsgEvent.TRData, TR)
        assert reply.result == MsgResult.Success

    def test_completeWithinDeadline(self):
        print("## test_completeWithinDeadline ##")
        TR = self.getNextTR()
        TR.deadline = self.getDeadline(10)
        reply = self.client.sendCmdExpectSuccess(MsgEvent.TRData, TR)
        assert reply.fields.missedDeadline is None
        assert reply.result == MsgResult.Success

    def test_missOneDeadline(self):
        print("## test_missOneDeadline ##")
        # Send a first request that misses the deadline
        TR = self.getNextTR()
        TR.deadline = self.getDeadline(0)
        reply = self.client.sendCmdExpectSuccess(MsgEvent.TRData, TR)
        assert reply.fields.missedDeadline is True
        assert reply.fields.threadId is not None

        # Send a second request that makes the deadline
        TR = self.getNextTR()
        TR.deadline = self.getDeadline(10)
        reply = self.client.sendCmdExpectSuccess(MsgEvent.TRData, TR)
        assert reply.fields.missedDeadline is None
        assert reply.result == MsgResult.Success

    def test_missTwoDeadlines(self):
        print("## test_missTwoDeadlines ##")
        # Send a first request that misses the deadline
        TR = self.getNextTR()
        TR.deadline = self.getDeadline(-1)
        TR.delay = 5  # introduce a processing delay on the server to make sure two deadlines miss
        reply = self.client.sendCmdExpectSuccess(MsgEvent.TRData, TR)
        assert reply.fields.missedDeadline is True
        assert reply.fields.threadId is not None

        # Send a second request that misses the deadline
        caughtRequestError = False
        TR = self.getNextTR()
        TR.deadline = self.getDeadline(0)
        try:
            reply = self.client.sendCmdExpectSuccess(MsgEvent.TRData, TR)
        except RequestError as err:
            caughtRequestError = True
            print("MissedMultipleDeadlines error fired as expected")
            assert re.search("MissedMultipleDeadlines", repr(err))
        assert caughtRequestError is True
