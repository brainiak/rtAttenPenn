"""
Messaging - Module to handle messaging between the client and server
"""
import socket
import struct
import logging
import pickle
from .StructDict import StructDict
from .MsgTypes import MsgType, MsgEvent
from .Errors import *

"""
Each message will be send in two parts, 1) header, 2) message
The header will have:
    - a magic value to validate we are in sync in the stream
    - a size to know how many bytes follow in the message
    - a message Id - monotonically increasing
    - a type and sub-type to do top-level validation and avoid unpickling garbage data
"""
# Header will be (Magic, ReqType, ReqEventType, Size)
hdrStruct = struct.Struct("!IHHI") # I=unsigned int, H=unsigned short
HDR_SIZE = hdrStruct.size
HDR_MAGIC = 0xFEEDFEED
MAX_DATA_SIZE = 1024*1024
MAX_META_SIZE = 1024

class Message():
    def __init__(self):
        self.type = MsgType.NoneType
        self.event_type = MsgEvent.NoneType
        self.id = -1
        self.fields = StructDict()
        self.data = None
    def __repr__(self):
        data_len = 0 if self.data is None else len(self.data)
        return "Message: Id:{} Type:({}, {}), fields {}, data size {}" \
            .format(self.id, self.type, self.event_type, self.fields, data_len)
    def set(self, msg_id, msg_type, msg_event):
        self.id = msg_id
        self.type = msg_type
        self.event_type = msg_event

class RtMessagingClient:
    """Messaging client for connecting to a server and sending messages"""
    def __init__(self, serverAddr, serverPort):
        self.addr = serverAddr
        self.port = serverPort
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn = socket.create_connection((self.addr, self.port))
    def __del__(self):
        if self.conn is not None:
            self.conn.close()
        self.socket.close()
    def sendRequest(self, msg):
        if self.conn is None:
            raise ConnectionError("RtMessagingClient: Connection is none")
        sendMsg(self.conn, msg)
    def getReply(self):
        if self.conn is None:
            raise ConnectionError("RtMessagingClient: Connection is none")
        msg = recvMsg(self.conn)
        return msg
    def close(self):
        if self.conn is not None:
            self.conn.close()
        self.socket.close()

class RtMessagingServer:
    """Messaging server, listening for connections and handling requests"""
    def __init__(self, port):
        # allocate socket and listen for connections
        logging.info("RtMessagingServer: listening on port: %r", port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', port))
        self.socket.listen(0)
        self.conn = None
    def __del__(self):
        self.socket.close()
    def getRequest(self):
        while True:
            try:
                if self.conn is None:
                    # accept a new connection
                    self.conn, _ = self.socket.accept()
                # read from the connection
                msg = recvMsg(self.conn)
                return msg
            except ConnectionAbortedError:
                break
            except OSError as err:
                logging.error(repr(err))
                if self.conn is not None:
                    self.conn.close()
                    self.conn = None
    def sendReply(self, msg):
        if self.conn == None:
            raise ConnectionError("RtMessagingServer: Connection is none")
        sendMsg(self.conn, msg)
    def close(self):
        if self.conn is not None:
            self.conn.close()
        self.socket.close()

def sendMsg(conn, msg):
    data = pickle.dumps(msg)
    hdr = hdrStruct.pack(HDR_MAGIC, msg.type, msg.event_type, len(data))
    conn.sendall(hdr)
    conn.sendall(data)

# header = (magic, msg_type, msg_event_type, msg_size)
def recvMsg(conn):
    packed_hdr = recvall(conn, HDR_SIZE)
    (magic, msg_type, msg_event_type, msg_size) = hdrStruct.unpack(packed_hdr)
    assert magic == HDR_MAGIC # TODO scan forward if we get out of sync
    data = recvall(conn, msg_size)
    # Do some basic validation before unpickling
    validateHeader(msg_type, msg_event_type, msg_size)
    msg = pickle.loads(data)
    return msg

def validateHeader(msg_type, msg_event_type, msg_size):
    if msg_type < MsgType.NoneType or msg_type >= MsgType.MaxType:
        raise MessageError("Invalid type {}".format(msg_type))
    elif msg_event_type < MsgEvent.NoneType or msg_type >= MsgEvent.MaxType:
        raise MessageError("Invalid event_type {}".format(msg_event_type))
    if msg_size > MAX_DATA_SIZE:
        raise MessageError("Message size exceeded {}".format(msg_size))
    if msg_size > MAX_META_SIZE:
        if msg_type != MsgType.Command or msg_event_type != MsgEvent.TrialData:
            raise MessageError("Invalid (type, size) ({}, {})".format(msg_event_type, msg_size))

def recvall(conn, count):
    buf = b''
    while count:
        newbuf = conn.recv(count)
        if not newbuf:
            raise socket.error("connection disconnected")
        buf += newbuf
        count -= len(newbuf)
    return buf
