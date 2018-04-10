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
    RetrieveData    = 36
    DeleteData      = 37
    StartSession    = 38
    EndSession      = 39
    StartRun        = 40
    EndRun          = 41
    TrainModel      = 42
    StartBlockGroup = 43
    EndBlockGroup   = 44
    StartBlock      = 45
    EndBlock        = 46
    TRData          = 47
    MaxType         = 48

class MsgResult:
    NoneType = 0
    Success  = 1
    Error    = 2
    MaxType  = 3
