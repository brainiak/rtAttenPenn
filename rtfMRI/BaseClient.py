from .RtfMRIClient import RtfMRIClient
from .StructDict import StructDict
from .MsgTypes import MsgEvent


class BaseClient(RtfMRIClient):
    def __init__(self):
        super().__init__()

    def runRun(self, runId):
        idx = runId - 1
        run = self.cfg.runs[idx]
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
