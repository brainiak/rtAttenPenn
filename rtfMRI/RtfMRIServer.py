"""
RtfMRIServer Module - Server handler for loading and running a model
  - Listens for requests from a client
  - An Init request loads the indicated model (e.g. base model, rtAtten model)
  - Receives and forwards client requests to the model for handling
  - Sends replies back to the client
"""
import logging
import threading
import time
from .BaseModel import BaseModel
from rtAtten.RtAttenModel import RtAttenModel
from .StructDict import StructDict
from .MsgTypes import MsgType, MsgEvent, MsgResult
from .utils import getGitCodeId
from .Messaging import RtMessagingServer, Message
from .Errors import RequestError, StateError, VersionError, RTError, MissedDeadlineError, MissedMultipleDeadlines


class RtfMRIServer():
    """Class for event handling on the server"""

    def __init__(self, port):
        self.messaging = RtMessagingServer(port)
        self.model = None
        self.deadlineThread = None
        self.threadReturnValue = {}  # a map of thread return values using threadId as key

    def threadMethod(self, msg):
        reply = self.model.handleMessage(msg)
        if msg.fields.cfg.delay is not None:
            # a delay that can be introduced for testing
            time.sleep(msg.fields.cfg.delay)
        self.threadReturnValue[threading.get_ident()] = reply

    def runThread(self, msg):
        # calculate seconds until deadline
        secondstil = msg.fields.cfg.deadline - time.time()
        # Check if a thread from the previous request is still running
        if self.deadlineThread:
            self.deadlineThread.join(timeout=secondstil)
            if self.deadlineThread.is_alive():
                # Previous analysis still not complete (server isn't keeping up)
                err1 = MissedMultipleDeadlines("Missed Multiple Deadlines")
                return errorReply(msg, err1)

        # Start the new task in a thread
        self.deadlineThread = threading.Thread(target=self.threadMethod, args=(msg,))
        self.deadlineThread.setDaemon(True)  # set to daemon so we don't need to join it
        self.deadlineThread.start()
        deadlineThreadId = self.deadlineThread.ident
        self.deadlineThread.join(timeout=secondstil)
        if (self.deadlineThread.is_alive() or secondstil < 0 or
                time.time() > msg.fields.cfg.deadline):
            # We missed the deadline, thread didn't complete in time
            err2 = MissedDeadlineError("Missed Deadline:")
            reply = warningReply(msg, err2, False)
            reply.fields.threadId = deadlineThreadId
        else:
            # Thread completed, we made the deadline
            reply = self.threadReturnValue.pop(deadlineThreadId)
        return reply

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
                        # if deadline is supplied, start handleMessage in a thread
                        # if no deadline supplied, run handleMessage natively
                        if msg.fields.cfg.deadline is None:
                            reply = self.model.handleMessage(msg)
                        else:
                            # run the handler in a timed thread
                            reply = self.runThread(msg)
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
                # TODO - remove all input requests for web interface (remove True)
                reply = warningReply(msg, err, True)
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


def warningReply(msg, error, requireResponse=False):
    rmsg = Message()
    rmsg.type = MsgType.Reply
    rmsg.result = MsgResult.Warning
    rmsg.fields.resp = requireResponse
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
