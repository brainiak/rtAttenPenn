"""A set of common message types for rtfMRI client and server"""


class MsgType:
    NoneType  = 11
    Init      = 12
    Command   = 13
    Reply     = 14
    Shutdown  = 15
    MaxType   = 16


class MsgEvent:
    NoneType        = 31
    StartExperiment = 32
    EndExperiment   = 33
    StartSession    = 34
    EndSession      = 35
    StartRun        = 36
    EndRun          = 37
    StartBlockGroup = 38
    EndBlockGroup   = 39
    StartBlock      = 40
    EndBlock        = 41
    TrialData       = 42
    TrainModel      = 43
    Success         = 44
    Error           = 45
    FeedSync        = 46
    MaxType         = 47
