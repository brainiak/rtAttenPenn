"""
RtfMRIClient - client side logic to run a rtfMRI experiment.
Uses a JSON experiment file to indicate how the experiment will be setup
and divided between Runs, BlockGroups, Blocks and Trials.
"""
from .Messaging import RtMessagingClient, Message
from .MsgTypes import MsgType, MsgEvent
from .StructDict import StructDict
from .Errors import *

class RtfMRIClient():
    """Class to handle parsing configuration and running the logic of the experiment"""

    def __init__(self, addr, port):
        self.msg_id = 0
        self.model = None
        self.id_fields = StructDict()
        self.messaging = RtMessagingClient(addr, port)

    def __del__(self):
        self.close()

    def initModel(self, model):
        self.model = model
        fields = StructDict()
        fields.modelType = model
        self.sendExpectSuccess(MsgType.Init, MsgEvent.NoneType, fields)

    def message(self, msg_type, msg_event):
        self.msg_id += 1
        msg = Message()
        msg.set(self.msg_id, msg_type, msg_event)
        return msg

    def run(self, cfg):
        validateExperimentCfg(cfg)
        self.id_fields = StructDict()
        self.id_fields.experimentId = cfg.experiment.experimentId
        self.sendExpectSuccess(MsgType.Command, MsgEvent.StartExperiment, cfg.experiment)
        self.id_fields.sessionId = cfg.session.sessionId
        self.sendExpectSuccess(MsgType.Command, MsgEvent.StartSession, cfg.session)
        for run in cfg.runs:
            self.id_fields.runId = run.runId
            self.sendExpectSuccess(MsgType.Command, MsgEvent.StartRun, run)
            for blockGroup in run.blockGroups:
                self.id_fields.blockGroupId = blockGroup.blockGroupId
                self.sendExpectSuccess(MsgType.Command, MsgEvent.StartBlockGroup, blockGroup)
                for block in blockGroup.blocks:
                    self.id_fields.blockId = block.blockId
                    self.sendExpectSuccess(MsgType.Command, MsgEvent.StartBlock, block)
                    trialRange = [int(x) for x in block.trials.split(':')]
                    assert len(trialRange) == 2
                    for trial_idx in range(trialRange[0], trialRange[1]):
                        self.id_fields.trialId = trial_idx
                        trial = StructDict({'trialId': trial_idx})
                        self.sendExpectSuccess(MsgType.Command, MsgEvent.TrialData, trial)
                    del self.id_fields.trialId
                    self.sendExpectSuccess(MsgType.Command, MsgEvent.EndBlock, block)
                del self.id_fields.blockId
                self.sendExpectSuccess(MsgType.Command, MsgEvent.EndBlockGroup, blockGroup)
            del self.id_fields.blockGroupId
            self.sendExpectSuccess(MsgType.Command, MsgEvent.EndRun, run)
        del self.id_fields.runId
        self.sendExpectSuccess(MsgType.Command, MsgEvent.EndSession, cfg.session)
        del self.id_fields.sessionId
        self.sendExpectSuccess(MsgType.Command, MsgEvent.EndExperiment, cfg.experiment)

    def sendShutdownServer(self):
        msg = self.message(MsgType.Shutdown, MsgEvent.NoneType)
        self.messaging.sendRequest(msg)

    def sendExpectSuccess(self, msg_type, msg_event, msg_fields, data=None):
        msg = self.message(msg_type, msg_event)
        msg.fields.update(self.id_fields)
        msg.fields.update(msg_fields)
        msg.data = data
        self.messaging.sendRequest(msg)
        reply = self.messaging.getReply()
        assert reply.id == msg.id
        assert reply.type == MsgType.Reply
        if reply.event_type != MsgEvent.Success:
            raise RequestError("type:{} event:{} fields:{}".format(msg_type, msg_event, msg.fields))

    def close(self):
        self.messaging.close()

def validateExperimentCfg(cfg):
    if cfg.experiment is None or cfg.experiment.experimentId is None:
        raise ValidationError("experimentId not defined")
    if cfg.session is None or cfg.session.sessionId is None:
        raise ValidationError("sessionId not defined")
    if cfg.runs is None:
        raise ValidationError("runs not defined")
    for ridx, run in enumerate(cfg.runs):
        if run.runId is None:
            raise ValidationError("runId not defined in runs[{}]".format(ridx))
        if run.blockGroups is None:
            raise ValidationError("blockGroups not defined in runs[{}]".format(ridx))
        for bgidx, blockGroup in enumerate(run.blockGroups):
            if blockGroup.blockGroupId is None:
                raise ValidationError("blockGroupId not defined in BG[{}]".format(bgidx))
            if blockGroup.blocks is None:
                raise ValidationError("blocks not defined in BG[{}]".format(bgidx))
            for blkidx, block in enumerate(blockGroup.blocks):
                if block.blockId is None:
                    raise ValidationError("blockId not defined in Block[{}]".format(blkidx))
                if block.trials is None:
                    raise ValidationError("trials not defined in Block[{}]".format(blkidx))
                trialRange = [int(x) for x in block.trials.split(':')]
                if len(trialRange) != 2 or trialRange[0] > trialRange[1]:
                    raise ValidationError("trial range invalid Block[{}]".format(blkidx))
    return True
