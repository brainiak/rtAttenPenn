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
    Ping            = 35
    SyncClock       = 36
    RetrieveData    = 37
    DeleteData      = 38
    StartSession    = 39
    EndSession      = 40
    StartRun        = 41
    EndRun          = 42
    TrainModel      = 43
    StartBlockGroup = 44
    EndBlockGroup   = 45
    StartBlock      = 46
    EndBlock        = 47
    TRData          = 48
    MaxType         = 49

class MsgResult:
    NoneType = 0
    Success  = 1
    Error    = 2
    Warning  = 3
    MaxType  = 4
