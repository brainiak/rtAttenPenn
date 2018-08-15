"""
RtfMRIClient - client side logic to run a rtfMRI session.
Uses a JSON configuration file to indicate how the session will be setup
and divided between Runs, BlockGroups, Blocks and Trials.
"""
import json
import toml  # type: ignore
import pathlib
import time
import re
import logging
from .StructDict import StructDict, recurseCreateStructDict
from .Messaging import RtMessagingClient, Message
from .utils import getGitCodeId
from .MsgTypes import MsgType, MsgEvent, MsgResult
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
        if self.messaging is not None:
            self.messaging.close()
        self.messaging = RtMessagingClient(addr, port)

    def disconnect(self):
        if self.messaging is not None:
            self.messaging.close()
            self.messaging = None

    def initModel(self, modelName):
        self.modelName = modelName
        msgfields = StructDict()
        msgfields.modelType = modelName
        msgfields.gitCodeId = getGitCodeId()
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

        # calculate clockSkew and round-trip time
        self.calculateclockSkew()

        self.id_fields = StructDict()
        self.id_fields.experimentId = cfg.experiment.experimentId
        self.id_fields.sessionId = cfg.session.sessionId
        self.id_fields.subjectNum = cfg.session.subjectNum
        self.id_fields.subjectDay = cfg.session.subjectDay
        logging.debug("Start session {}".format(cfg.session.sessionId))
        self.sendCmdExpectSuccess(MsgEvent.StartSession, cfg.session)

    def endSession(self):
        session = StructDict()
        session.ids = self.cfg.session.ids
        self.sendCmdExpectSuccess(MsgEvent.EndSession, session)

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
        # TODO change from assert to error
        assert reply.type == MsgType.Reply
        assert reply.event_type == msg.event_type
        if reply.result != MsgResult.Success:
            reasonStr = ''
            if isinstance(reply.data, str):
                reasonStr = reply.data
            elif len(reply.data) < 1024:
                reasonStr = str(reply.data, 'utf-8')

            if reply.result == MsgResult.Warning:
                if reply.fields.resp is True:
                    resp = input("WARNING!!: {}. Continue? Y/N [N]:".format(reasonStr))
                    if resp.upper() != 'Y':
                        raise RequestError("type:{} event:{} fields:{}: {}".format(
                            msg_type, msg_event, msg.fields, reasonStr))
                elif re.search("MissedDeadlineError", reasonStr):
                    logging.warning("Missed Deadline: Msg {}".format(msg.fields.ids))
                    reply.fields.missedDeadline = True
                    if reply.fields.outputlns is None:
                        reply.fields.outputlns = []
                    ids = msg.fields.ids
                    outStr = "{:d}\t{:d}\t{:d}\t## Missed Deadline ##".format(ids.runId, ids.blockId, ids.trId)
                    reply.fields.outputlns.append(outStr)
                else:
                    logging.warning(reasonStr)
                    print("WARNING!!: {}".format(reasonStr))
            else:
                raise RequestError("type:{} event:{} fields:{}: {}".format(
                    msg_type, msg_event, msg.fields, reasonStr))
        assert reply.id == msg.id
        return reply

    def sendCmdExpectSuccess(self, msg_event, msg_fields, data=None):
        return self.sendExpectSuccess(MsgType.Command, msg_event, msg_fields, data)

    def calculateclockSkew(self):
        RTT_list = []
        clockSkew_list = []
        time_fields = StructDict()
        numIters = 30
        if self.cfg.session.calcClockSkewIters is not None:
            numIters = self.cfg.session.calcClockSkewIters
        for _ in range(numIters):
            time_fields.clientTime1 = time.time()
            reply = self.sendCmdExpectSuccess(MsgEvent.SyncClock, time_fields)
            time_fields.clientTime2 = time.time()
            ServerTimeStamp = reply.fields.serverTime
            # Clock Skew Formula from
            # "Improved Algorithms for Synchronizing Computer Network Clocks"
            # by: David Mills, Transactions on Networking, June 1995
            a = ServerTimeStamp - time_fields.clientTime1
            b = ServerTimeStamp - time_fields.clientTime2
            RTT = a - b
            clockSkew = (a + b)/2
            RTT_list.append(RTT)
            clockSkew_list.append(clockSkew)
            self.cfg.minRTT = min(RTT_list)
            self.cfg.maxRTT = max(RTT_list)
            self.cfg.clockSkew = clockSkew_list[RTT_list.index(self.cfg.minRTT)]
            avgRTT = sum(RTT_list) / float(len(RTT_list))
        logging.info("MaxRTT {:.3f}s, MinRTT {:.3f}, AvgRTT {:.3f}, ClockSkew {:.3f}s".\
                     format(self.cfg.maxRTT, self.cfg.minRTT, avgRTT, self.cfg.clockSkew))

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
    if cfg.experiment is None:
        raise ValidationError("config.experiment is not defined")
    if cfg.session is None:
        raise ValidationError("config.session is not defined")
    if cfg.session.sessionId is None:
        raise ValidationError("sessionId not defined")
    if not cfg.session.rtData and not cfg.session.replayMatFileMode:
        raise ValidationError("Must set either rtData or replayMatFileMode")
    return True


def validateRunCfg(run):
    if run.runId is None:
        raise ValidationError("runId not defined")
    if run.scanNum is None or run.scanNum < 0:
        raise ValidationError("scanNum not defined")
    if run.blockGroups is None:
        raise ValidationError(
            "blockGroups not defined in run {}".format(run.runId))
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
