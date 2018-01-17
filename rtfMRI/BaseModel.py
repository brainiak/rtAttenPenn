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
from .Errors import *

class BaseModel():
    def __init__(self):
        self.experimentId = -1
        self.sessionId = -1
        self.runId = -1
        self.blockGroupId = -1
        self.blockId = -1
        self.trialId = -1
        self.blockType = -1

    def resetState(self):
        self.experimentId = -1
        self.sessionId = -1
        self.runId = -1
        self.blockGroupId = -1
        self.blockId = -1
        self.trialId = -1
        self.blockType = -1

    def handleMessage(self, msg):
        self.validateMsg(msg)
        reply = None
        if msg.event_type == MsgEvent.StartExperiment:
            reply = self.StartExperiment(msg)
        elif msg.event_type == MsgEvent.EndExperiment:
            reply = self.EndExperiment(msg)
        elif msg.event_type == MsgEvent.StartSession:
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
        elif msg.event_type == MsgEvent.TrialData:
            reply = self.TrialData(msg)
        elif msg.event_type == MsgEvent.TrainModel:
            reply = self.TrainModel(msg)
        else:
            reply = self.createReplyMessage(msg.id, MsgEvent.Error)
        return reply

    def validateMsg(self, msg):
        if msg.event_type > MsgEvent.StartExperiment:
            if msg.fields.experimentId != self.experimentId:
                raise ValidationError("experimentId mismatch {} {}"\
                    .format(self.experimentId, msg.fields.experimentId))
        if msg.event_type > MsgEvent.StartSession:
            if msg.fields.sessionId != self.sessionId:
                raise ValidationError("sessionId mismatch {} {}"\
                    .format(self.sessionId, msg.fields.sessionId))
        if msg.event_type > MsgEvent.StartRun:
            if msg.fields.runId != self.runId:
                raise ValidationError("runId mismatch {} {}"\
                    .format(self.runId, msg.fields.runId))
        if msg.event_type > MsgEvent.StartBlockGroup:
            if msg.fields.blockGroupId != self.blockGroupId:
                raise ValidationError("blockGroupId mismatch {} {}"\
                    .format(self.blockId, msg.fields.blockId))
        if msg.event_type > MsgEvent.StartBlock:
            if msg.fields.blockId != self.blockId:
                raise ValidationError("blockId mismatch {} {}"\
                    .format(self.blockId, msg.fields.blockId))
        return

    def createReplyMessage(self, msg_id, event_type):
        rmsg = Message()
        rmsg.id = msg_id
        rmsg.type = MsgType.Reply
        rmsg.event_type = event_type
        rmsg.fields.experimentId = self.experimentId
        rmsg.fields.sessionId = self.sessionId
        rmsg.fields.runId = self.runId
        rmsg.fields.blockGroupId = self.blockGroupId
        rmsg.fields.blockId = self.blockId
        rmsg.fields.trialId = self.trialId
        rmsg.fields.blockType = self.blockType
        return rmsg

    def StartExperiment(self, msg):
        self.resetState()
        self.experimentId = msg.fields.experimentId
        logging.info("Start Experiment: %s", self.experimentId)
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def EndExperiment(self, msg):
        self.resetState()
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def StartSession(self, msg):
        self.sessionId = msg.fields.sessionId
        self.runId = -1
        logging.info("Start Session: %s", self.sessionId)
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def EndSession(self, msg):
        self.sessionId = -1
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def StartRun(self, msg):
        self.runId = msg.fields.runId
        self.blockGroupId = -1
        logging.info("Start Run: %s", self.runId)
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def EndRun(self, msg):
        self.runId = -1
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def StartBlockGroup(self, msg):
        self.blockGroupId = msg.fields.blockGroupId
        self.blockId = -1
        logging.info("Start BlockGroup: %s", self.blockGroupId)
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def EndBlockGroup(self, msg):
        self.blockGroupId = -1
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def StartBlock(self, msg):
        self.blockId = msg.fields.blockId
        self.trialId = -1
        logging.info("Start Block: %s", self.blockId)
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def EndBlock(self, msg):
        self.blockId = -1
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def TrialData(self, msg):
        self.trialId = msg.fields.trialId
        logging.info("Trial: %s", self.trialId)
        # if self.blockType == BlockType.Train:
        #     reply = self.model.TrainingData(msg)
        # elif msg.event_type == BlockType.Predict:
        #     reply = self.model.Predict(msg)
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def TrainModel(self, msg):
        # reply = self.model.TrainModel(msg)
        return self.createReplyMessage(msg.id, MsgEvent.Success)
