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
    FeedSync        = 34
    RetrieveData    = 35
    StartSession    = 36
    EndSession      = 37
    StartRun        = 38
    EndRun          = 39
    TrainModel      = 40
    StartBlockGroup = 41
    EndBlockGroup   = 42
    StartBlock      = 43
    EndBlock        = 44
    TRData          = 45
    MaxType         = 46

class MsgResult:
    NoneType = 0
    Success  = 1
    Error    = 2
    MaxType  = 3
