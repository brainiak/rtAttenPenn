"""
RtfMRIServer Module - Server handler for loading and running a model
  - Listens for requests from a client
  - An Init request loads the indicated model (e.g. base model, rtAtten model)
  - Receives and forwards client requests to the model for handling
  - Sends replies back to the client
"""
import logging
from .BaseModel import BaseModel
from .rtAtten.RtAttenModel import RtAttenModel
from .MsgTypes import MsgType, MsgEvent
from .Messaging import RtMessagingServer, Message
from .Errors import RequestError, StateError, RTError


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
                msg = self.messaging.getRequest()
                reply = successReply(msg.id)
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
                elif msg.type == MsgType.Command:
                    if self.model is None:
                        raise StateError("No model object exists")
                    reply = self.model.handleMessage(msg)
                    if reply is None:
                        raise ValueError("Reply is None for msg %r" % (msg.type))
                elif msg.type == MsgType.Shutdown:
                    break
                else:
                    raise RequestError(
                        "unknown request type '{}'".format(msg.type))
            except RTError as err:
                logging.warn("RtfMRIServer:RunEventLoop: %r", err)
                msg_id = 0 if msg is None else msg.id
                reply = errorReply(msg_id, err)
            except KeyError as err:
                logging.warn("RtfMRIServer:RunEventLoop: %r", err)
                msg_id = 0 if msg is None else msg.id
                reply = errorReply(msg_id, RTError(
                    "Field not found: {}".format(err)))
            self.messaging.sendReply(reply)
        return True


def errorReply(msgId, error):
    msg = Message()
    msg.id = msgId
    msg.type = MsgType.Reply
    msg.event_type = MsgEvent.Error
    msg.data = repr(error).encode()
    return msg


def successReply(msgId):
    msg = Message()
    msg.id = msgId
    msg.type = MsgType.Reply
    msg.event_type = MsgEvent.Success
    msg.data = b''
    return msg
