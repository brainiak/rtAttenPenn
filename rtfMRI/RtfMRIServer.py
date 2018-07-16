"""
RtfMRIServer Module - Server handler for loading and running a model
  - Listens for requests from a client
  - An Init request loads the indicated model (e.g. base model, rtAtten model)
  - Receives and forwards client requests to the model for handling
  - Sends replies back to the client
"""
import logging
import time
from .BaseModel import BaseModel
from rtAtten.RtAttenModel import RtAttenModel
from .StructDict import StructDict
from .MsgTypes import MsgType, MsgEvent, MsgResult
from .utils import getGitCodeId
from .Messaging import RtMessagingServer, Message
from .Errors import RequestError, StateError, VersionError, RTError


class RtfMRIServer():
    """Class for event handling on the server"""

    def __init__(self, port):
        self.messaging = RtMessagingServer(port)
        self.model = None

    def RunEventLoop(self):
        while True:
            msg = None
            reply = None
            try:
                msg = self.messaging.getRequest()  # can raise MessageError, PickleError
                reply = successReply(msg)
                if msg.type == MsgType.Init:
                    modelType = msg.fields.cfg.modelType
                    if modelType == 'base':
                        logging.info("RtfMRIServer: init base model")
                        self.model = BaseModel()
                    elif modelType == 'rtAtten':
                        logging.info("RtfMRIServer: init rtAtten model")
                        self.model = RtAttenModel()
                    else:
                        raise RequestError(
                            "unknown model type '{}'".
                            format(modelType))
                    # Check that source code versions match
                    clientGitCodeId = msg.fields.cfg.gitCodeId
                    serverGitCodeId = getGitCodeId()
                    if serverGitCodeId != clientGitCodeId:
                        raise VersionError("Mismatching gitCodeId {} {}".
                                           format(clientGitCodeId, serverGitCodeId))
                elif msg.type == MsgType.Command:
                    if msg.event_type == MsgEvent.Ping:
                        reply = successReply(msg)
                    elif msg.event_type == MsgEvent.SyncClock:
                        reply = successReply(msg)
                        reply.fields = StructDict()
                        reply.fields.serverTime = time.time()
                    elif self.model is not None:
                        reply = self.model.handleMessage(msg)
                    else:
                        raise StateError("No model object exists")
                    if reply is None:
                        raise RequestError("Reply is None for msg %r" % (msg.type))
                elif msg.type == MsgType.Shutdown:
                    break
                else:
                    raise RequestError(
                        "unknown request type '{}'".format(msg.type))
            except VersionError as err:
                reply = warningReply(msg, err)
            except RTError as err:
                logging.error("RtfMRIServer:RunEventLoop: %r", err)
                reply = errorReply(msg, err)
            except KeyError as err:
                logging.error("RtfMRIServer:RunEventLoop: %r", err)
                reply = errorReply(msg, RTError(
                    "Msg field missing: {}".format(err)))
            self.messaging.sendReply(reply)
        return True


def errorReply(msg, error):
    rmsg = Message()
    rmsg.type = MsgType.Reply
    rmsg.result = MsgResult.Error
    if msg is not None:
        rmsg.id = msg.id
        rmsg.event_type = msg.event_type
        rmsg.data = repr(error).encode()
    else:
        rmsg.id = 0
        rmsg.event_type = MsgEvent.NoneType
    return rmsg


def warningReply(msg, error):
    rmsg = Message()
    rmsg.type = MsgType.Reply
    rmsg.result = MsgResult.Warning
    if msg is not None:
        rmsg.id = msg.id
        rmsg.event_type = msg.event_type
        rmsg.data = repr(error).encode()
    else:
        rmsg.id = 0
        rmsg.event_type = MsgEvent.NoneType
    return rmsg


def successReply(msg):
    rmsg = Message()
    rmsg.id = msg.id
    rmsg.type = MsgType.Reply
    rmsg.event_type = msg.event_type
    rmsg.result = MsgResult.Success
    rmsg.data = b''
    return rmsg
