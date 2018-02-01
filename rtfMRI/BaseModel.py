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
import logging
from .Messaging import Message
from .MsgTypes import MsgType, MsgEvent
from .Errors import ValidationError
from .StructDict import StructDict


class BaseModel():
    def __init__(self):
        self.id_fields = StructDict()
        self.id_fields.experimentId = -1
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

    def handleMessage(self, msg):
        self.validateMsg(msg)
        reply = None
        if msg.event_type == MsgEvent.StartSession:
            reply = self.StartSession(msg)
        elif msg.event_type == MsgEvent.EndSession:
            reply = self.EndSession(msg)
        elif msg.event_type == MsgEvent.StartRun:
            reply = self.StartRun(msg)
        elif msg.event_type == MsgEvent.EndRun:
            reply = self.EndRun(msg)
        elif msg.event_type == MsgEvent.StartBlockGroup:
            reply = self.StartBlockGroup(msg)
        elif msg.event_type == MsgEvent.EndBlockGroup:
            reply = self.EndBlockGroup(msg)
        elif msg.event_type == MsgEvent.StartBlock:
            reply = self.StartBlock(msg)
        elif msg.event_type == MsgEvent.EndBlock:
            reply = self.EndBlock(msg)
        elif msg.event_type == MsgEvent.TRData:
            reply = self.TRData(msg)
        elif msg.event_type == MsgEvent.TrainModel:
            reply = self.TrainModel(msg)
        else:
            reply = self.createReplyMessage(msg.id, MsgEvent.Error)
        return reply

    def validateMsg(self, msg):
        if msg.event_type > MsgEvent.StartSession:
            if msg.fields.ids.experimentId != self.id_fields.experimentId:
                raise ValidationError("experimentId mismatch {} {}"
                                      .format(self.id_fields.experimentId,
                                              msg.fields.ids.experimentId))
            if msg.fields.ids.sessionId != self.id_fields.sessionId:
                raise ValidationError("sessionId mismatch {} {}"
                                      .format(self.id_fields.sessionId,
                                              msg.fields.ids.sessionId))
        if msg.event_type > MsgEvent.StartRun:
            if msg.fields.ids.runId != self.id_fields.runId:
                raise ValidationError("runId mismatch {} {}"
                                      .format(self.id_fields.runId, msg.fields.ids.runId))
        if msg.event_type > MsgEvent.StartBlockGroup:
            if msg.fields.ids.blkGrpId != self.id_fields.blkGrpId:
                raise ValidationError("blkGrpId mismatch {} {}"
                                      .format(self.id_fields.blockId,
                                              msg.fields.ids.blockId))
        if msg.event_type > MsgEvent.StartBlock:
            if msg.fields.ids.blockId != self.id_fields.blockId:
                raise ValidationError("blockId mismatch {} {}"
                                      .format(self.id_fields.blockId,
                                              msg.fields.ids.blockId))
        return

    def createReplyMessage(self, msg_id, event_type):
        rmsg = Message()
        rmsg.id = msg_id
        rmsg.type = MsgType.Reply
        rmsg.event_type = event_type
        rmsg.fields.ids = self.id_fields.copy()
        # remove ids with -1
        rm_keys = [k for k, val in rmsg.fields.ids.items() if val == -1]
        for key in rm_keys:
            del(rmsg.fields.ids[key])
        rmsg.fields.blockType = self.blockType
        return rmsg

    def StartSession(self, msg):
        self.resetState()
        self.id_fields.experimentId = msg.fields.ids.experimentId
        self.id_fields.sessionId = msg.fields.ids.sessionId
        logging.info("Start Session: %s", self.id_fields.sessionId)
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def EndSession(self, msg):
        self.resetState()
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def StartRun(self, msg):
        self.id_fields.runId = msg.fields.ids.runId
        self.id_fields.blkGrpId = -1
        logging.info("Start Run: %s", self.id_fields.runId)
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def EndRun(self, msg):
        self.id_fields.runId = -1
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def StartBlockGroup(self, msg):
        self.id_fields.blkGrpId = msg.fields.ids.blkGrpId
        self.id_fields.blockId = -1
        logging.info("Start BlockGroup: %s", self.id_fields.blkGrpId)
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def EndBlockGroup(self, msg):
        self.id_fields.blkGrpId = -1
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def StartBlock(self, msg):
        self.id_fields.blockId = msg.fields.ids.blockId
        self.id_fields.trId = -1
        logging.info("Start Block: %s", self.id_fields.blockId)
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def EndBlock(self, msg):
        self.id_fields.blockId = -1
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def TRData(self, msg):
        self.id_fields.trId = msg.fields.ids.trId
        logging.debug("Trial: %s", self.id_fields.trId)
        # if self.blockType == BlockType.Train:
        #     reply = self.model.TrainingData(msg)
        # elif msg.event_type == BlockType.Predict:
        #     reply = self.model.Predict(msg)
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def TrainModel(self, msg):
        logging.info("TrainModel run %d", msg.fields.ids.runId)
        return self.createReplyMessage(msg.id, MsgEvent.Success)
