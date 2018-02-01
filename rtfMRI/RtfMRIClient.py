"""
RtfMRIClient - client side logic to run a rtfMRI session.
Uses a JSON configuration file to indicate how the session will be setup
and divided between Runs, BlockGroups, Blocks and Trials.
"""
import json
import toml  # type: ignore
import pathlib
from .StructDict import StructDict, recurseCreateStructDict
from .Messaging import RtMessagingClient, Message
from .MsgTypes import MsgType, MsgEvent
from .Errors import ValidationError, RequestError, InvocationError


class RtfMRIClient():
    """
    Class to handle parsing configuration and running the session logic
    """

    def __init__(self, settings):
        self.msg_id = 0
        self.id_fields = StructDict()
        self.model = settings.model
        self.messaging = RtMessagingClient(settings.addr, settings.port)

    def __del__(self):
        self.close()

    def initModel(self):
        msgfields = StructDict()
        msgfields.modelType = self.model
        self.sendExpectSuccess(MsgType.Init, MsgEvent.NoneType, msgfields)

    def message(self, msg_type, msg_event):
        self.msg_id += 1
        msg = Message()
        msg.set(self.msg_id, msg_type, msg_event)
        return msg

    def runSession(self, experiment_file):
        cfg = loadConfigFile(experiment_file)
        validateSessionCfg(cfg)
        self.id_fields = StructDict()
        self.id_fields.experimentId = cfg.session.experimentId
        self.id_fields.sessionId = cfg.session.sessionId
        self.sendCmdExpectSuccess(MsgEvent.StartSession, cfg.session)
        for run in cfg.runs:
            self.id_fields.runId = run.runId
            self.sendCmdExpectSuccess(MsgEvent.StartRun, run)
            for blockGroup in run.blockGroups:
                self.id_fields.blkGrpId = blockGroup.blkGrpId
                self.sendCmdExpectSuccess(MsgEvent.StartBlockGroup, blockGroup)
                for block in blockGroup.blocks:
                    self.id_fields.blockId = block.blockId
                    self.sendCmdExpectSuccess(MsgEvent.StartBlock, block)
                    trialRange = [int(x) for x in block.TRs.split(':')]
                    assert len(trialRange) == 2
                    for trial_idx in range(trialRange[0], trialRange[1]):
                        self.id_fields.trId = trial_idx
                        trial = StructDict({'trId': trial_idx})
                        self.sendCmdExpectSuccess(MsgEvent.TRData, trial)
                    del self.id_fields.trId
                    self.sendCmdExpectSuccess(MsgEvent.EndBlock, block)
                del self.id_fields.blockId
                self.sendCmdExpectSuccess(MsgEvent.EndBlockGroup, blockGroup)
            del self.id_fields.blkGrpId
            self.sendCmdExpectSuccess(MsgEvent.EndRun, run)
        del self.id_fields.runId
        self.sendCmdExpectSuccess(MsgEvent.EndSession, cfg.session)

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

    def sendCmdExpectSuccess(self, msg_event, msg_fields, data=None):
        self.sendExpectSuccess(MsgType.Command, msg_event, msg_fields, data)

    def close(self):
        self.messaging.close()


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
