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
    Success         = 32
    Error           = 33
    FeedSync        = 34
    StartSession    = 35
    EndSession      = 36
    StartRun        = 37
    EndRun          = 38
    TrainModel      = 39
    StartBlockGroup = 40
    EndBlockGroup   = 41
    StartBlock      = 42
    EndBlock        = 43
    TRData          = 44
    MaxType         = 45
