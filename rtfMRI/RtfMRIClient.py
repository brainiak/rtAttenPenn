"""
RtfMRIClient - client side logic to run a rtfMRI session.
Uses a JSON configuration file to indicate how the session will be setup
and divided between Runs, BlockGroups, Blocks and Trials.
"""
import json
import toml  # type: ignore
import pathlib
import logging
from .StructDict import StructDict, recurseCreateStructDict
from .Messaging import RtMessagingClient, Message
from .MsgTypes import MsgType, MsgEvent
from .Errors import ValidationError, RequestError, InvocationError


class RtfMRIClient():
    """
    Class to handle parsing configuration and running the session logic
    """

    def __init__(self):
        self.modelName = ''
        self.cfg = None
        self.msg_id = 0
        self.messaging = None
        self.id_fields = StructDict()

    def __del__(self):
        self.close()

    def connect(self, addr, port):
        self.messaging = RtMessagingClient(addr, port)

    def disconnect(self):
        if self.messaging is not None:
            self.messaging.close()
            self.messaging = None

    def initModel(self, modelName):
        self.modelName = modelName
        msgfields = StructDict()
        msgfields.modelType = modelName
        logging.debug("Init Model {}".format(modelName))
        self.sendExpectSuccess(MsgType.Init, MsgEvent.NoneType, msgfields)

    def message(self, msg_type, msg_event):
        self.msg_id += 1
        msg = Message()
        msg.set(self.msg_id, msg_type, msg_event)
        return msg

    def initSession(self, cfg):
        self.cfg = cfg
        validateSessionCfg(cfg)
        self.modelName = cfg.experiment.model
        self.initModel(self.modelName)

        self.id_fields = StructDict()
        self.id_fields.experimentId = cfg.experiment.experimentId
        self.id_fields.sessionId = cfg.session.sessionId
        self.id_fields.subjectNum = cfg.session.subjectNum
        self.id_fields.subjectDay = cfg.session.subjectDay
        logging.debug("Start session {}".format(cfg.session.sessionId))
        self.sendCmdExpectSuccess(MsgEvent.StartSession, cfg.session)

    def endSession(self):
        self.sendCmdExpectSuccess(MsgEvent.EndSession, self.cfg.session)

    def doRuns(self):
        # Process each run
        for idx, _ in enumerate(self.cfg.runs):
            self.runRun(idx+1)

    def runRun(self, runId):
        pass

    def sendShutdownServer(self):
        msg = self.message(MsgType.Shutdown, MsgEvent.NoneType)
        self.messaging.sendRequest(msg)

    def sendExpectSuccess(self, msg_type, msg_event, msg_fields, data=None):
        msg = self.message(msg_type, msg_event)
        msg.fields.ids = self.id_fields
        msg.fields.cfg = msg_fields
        msg.data = data
        self.messaging.sendRequest(msg)
        reply = self.messaging.getReply()
        assert reply.type == MsgType.Reply
        if reply.event_type != MsgEvent.Success:
            raise RequestError("type:{} event:{} fields:{}: {}".format(
                msg_type, msg_event, msg.fields, str(reply.data, 'utf-8')))
        assert reply.id == msg.id
        return reply

    def sendCmdExpectSuccess(self, msg_event, msg_fields, data=None):
        return self.sendExpectSuccess(MsgType.Command, msg_event, msg_fields, data)

    def close(self):
        self.disconnect()


def loadConfigFile(filename):
    file_suffix = pathlib.Path(filename).suffix
    if file_suffix == '.json':
        # load json
        with open(filename) as fp:
            cfg_dict = json.load(fp)
        # to write out config
        # with open('t1.json', 'w+') as fd:
        #   json.dump(cfg, fd, indent=2)
    elif file_suffix == '.toml':
        # load toml
        cfg_dict = toml.load(filename)
        # to write out config
        # with open('t1.toml', 'w+') as fd:
        #  toml.dump(cfg, fd)
    else:
        raise InvocationError("experiment file requires to be .json or .toml")
    cfg_struct = recurseCreateStructDict(cfg_dict)
    return cfg_struct


def validateSessionCfg(cfg):
    if cfg.session is None or cfg.session.sessionId is None:
        raise ValidationError("sessionId not defined")
    if cfg.runs is None:
        raise ValidationError("runs not defined")
    for ridx, run in enumerate(cfg.runs):
        if run.runId is None:
            raise ValidationError("runId not defined in runs[{}]".format(ridx))
        if run.blockGroups is None:
            raise ValidationError(
                "blockGroups not defined in runs[{}]".format(ridx))
        for bgidx, blockGroup in enumerate(run.blockGroups):
            if blockGroup.blkGrpId is None:
                raise ValidationError(
                    "blkGrpId not defined in BG[{}]".format(bgidx))
            if blockGroup.blocks is None:
                raise ValidationError(
                    "blocks not defined in BG[{}]".format(bgidx))
            for blkidx, block in enumerate(blockGroup.blocks):
                if block.blockId is None:
                    raise ValidationError(
                        "blockId not defined in Block[{}]".format(blkidx))
                if block.TRs is None:
                    raise ValidationError(
                        "TRs not defined in Block[{}]".format(blkidx))
                # trialRange = [int(x) for x in block.TRs.split(':')]
                # if len(trialRange) != 2 or trialRange[0] > trialRange[1]:
                #     raise ValidationError(
                #         "trial range invalid Block[{}]".format(blkidx))
    return True
