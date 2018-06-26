"""
BaseModel - Generic experiment model for RT fMRI studies
An experiment is comprised as follows:
    - Experiment (i.e. a subject over multiple days)
      - Session (1 or more sessions, each on a different day)
        - Runs (1 or more runs per session)
          - BlockGroups (1 or more grouping of multiple blocks into a set)
            - Blocks (1 or more blocks per run)
              - Trial (1 or more data scans recieved per block)
"""
import os
import logging
from rtfMRI.Errors import ValidationError, RequestError
from rtfMRI.StructDict import StructDict

maxFileTransferSize = 1024**3  # 1 GB


class Event:
    NoneType        = 35
    RetrieveData    = 36
    DeleteData      = 37
    StartSession    = 38
    EndSession      = 39
    StartRun        = 40
    EndRun          = 41
    TrainModel      = 42
    StartBlockGroup = 43
    EndBlockGroup   = 44
    StartBlock      = 45
    EndBlock        = 46
    TRData          = 47
    MaxType         = 48


class BaseModel_Ray():
    def __init__(self):
        self.id_fields = StructDict()
        self.id_fields.experimentId = 0
        self.id_fields.sessionId = -1
        self.id_fields.runId = -1
        self.id_fields.blkGrpId = -1
        self.id_fields.blockId = -1
        self.id_fields.trId = -1
        self.blockType = -1

    def resetState(self):
        self.id_fields.experimentId = -1
        self.id_fields.sessionId = -1
        self.id_fields.runId = -1
        self.id_fields.blkGrpId = -1
        self.id_fields.blockId = -1
        self.id_fields.trId = -1
        self.blockType = -1

    def StartSession(self, sessionId):
        self.resetState()
        self.id_fields.sessionId = sessionId
        logging.info("Start Session: %s", self.id_fields.sessionId)
        reply = makeReply(True)
        return reply

    def EndSession(self):
        self.resetState()
        reply = makeReply(True)
        return reply

    def StartRun(self, runId):
        self.id_fields.runId = runId
        self.id_fields.blkGrpId = -1
        logging.info("Start Run: %s", self.id_fields.runId)
        reply = makeReply(True)
        return reply

    def EndRun(self):
        self.id_fields.runId = -1
        reply = makeReply(True)
        return reply

    def StartBlockGroup(self, blkGrpId):
        self.id_fields.blkGrpId = blkGrpId
        self.id_fields.blockId = -1
        logging.info("Start BlockGroup: %s", self.id_fields.blkGrpId)
        reply = makeReply(True)
        return reply

    def EndBlockGroup(self):
        self.id_fields.blkGrpId = -1
        reply = makeReply(True)
        return reply

    def StartBlock(self, id_fields):
        self.id_fields.blockId = id_fields.blockId
        self.id_fields.trId = -1
        logging.info("Start Block: %s", self.id_fields.blockId)
        reply = makeReply(True)
        return reply

    def EndBlock(self):
        self.id_fields.blockId = -1
        reply = makeReply(True)
        return reply

    def TRData(self, trId):
        self.id_fields.trId = trId
        logging.debug("Trial: %s", self.id_fields.trId)
        # if self.blockType == BlockType.Train:
        #     reply = self.model.TrainingData(msg)
        # elif msg.event_type == BlockType.Predict:
        #     reply = self.model.Predict(msg)
        reply = makeReply(True)
        return reply

    def TrainModel(self, runId):
        logging.info("TrainModel run %d", runId)
        reply = makeReply(True)
        return reply

    def RetrieveData(self, filename):
        reply = makeReply(True)
        reply.data = None
        try:
            filesize = os.path.getsize(filename)
            if filesize > maxFileTransferSize:
                raise RequestError("file %s, size %d exceeds max size %d" % (filename, filesize, maxFileTransferSize))
            logging.info("Reading file %s, size %d" % (filename, filesize))
            with open(filename, 'rb') as fh:
                reply.data = fh.read()
        except Exception as err:
            reply.success = False
            reply.errorMsg = "Error reading file: %s: %s" % (filename, str(err))
        return reply

    def DeleteData(self, filename):
        # Not implemented yet
        errorReply = makeReply(False)
        return errorReply

    def validateMsg(self, event_type, id_fields):
        if event_type > Event.StartSession:
            if id_fields.experimentId != self.id_fields.experimentId:
                raise ValidationError("experimentId mismatch {} {}"
                                      .format(self.id_fields.experimentId,
                                              id_fields.experimentId))
            if id_fields.sessionId != self.id_fields.sessionId:
                raise ValidationError("sessionId mismatch {} {}"
                                      .format(self.id_fields.sessionId,
                                              id_fields.sessionId))
        if event_type > Event.StartRun:
            if id_fields.runId != self.id_fields.runId:
                raise ValidationError("runId mismatch {} {}"
                                      .format(self.id_fields.runId, id_fields.runId))
        if event_type > Event.StartBlockGroup:
            if id_fields.blkGrpId != self.id_fields.blkGrpId:
                raise ValidationError("blkGrpId mismatch {} {}"
                                      .format(self.id_fields.blockId,
                                              id_fields.blockId))
        if event_type > Event.StartBlock:
            if id_fields.blockId != self.id_fields.blockId:
                raise ValidationError("blockId mismatch {} {}"
                                      .format(self.id_fields.blockId,
                                              id_fields.blockId))
        return


def makeReply(success):
    reply = StructDict()
    reply.success = success
    reply.outputlns = []
    return reply
