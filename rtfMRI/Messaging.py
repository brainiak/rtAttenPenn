"""
Messaging - Module to handle messaging between the client and server
"""
import socket
import ssl
import os
import struct
import logging
import pickle
from .StructDict import StructDict
from .MsgTypes import MsgType, MsgEvent, MsgResult
from .Errors import MessageError, ValidationError

"""
Each message will be send in two parts, 1) header, 2) message
The header will have:
    - a magic value to validate we are in sync in the stream
    - a size to know how many bytes follow in the message
    - a message Id - monotonically increasing
    - a (type, sub-type) for top-level validation to avoid
        unpickling garbage data
"""
# Header will be (Magic, ReqType, ReqEventType, Size)
hdrStruct = struct.Struct("!IHHI")  # I=unsigned int, H=unsigned short
HDR_SIZE = hdrStruct.size
HDR_MAGIC = 0xFEEDFEED

MAX_META_SIZE = 64 * 1024
MAX_TR_SIZE = 1024**2  # 1 MB
MAX_SESSION_SIZE = 1024**2  # 1 MB
MAX_DATA_SIZE = 1024**3  # 1 GB

useSSL = True
sslCertFile = 'rtfMRI.crt'
sslPrivateKey = 'rtfMRI_rsa.private'
certsDir = 'certs'


class Message():
    def __init__(self):
        self.type = MsgType.NoneType
        self.event_type = MsgEvent.NoneType
        self.result = MsgResult.NoneType
        self.id = -1
        self.fields = StructDict()
        self.data = b''

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
        if useSSL:
            certfile = getCertPath()
            self.sslContext = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=certfile)
            self.socket = self.sslContext.wrap_socket(self.socket, server_hostname='rtAtten')
        self.socket.connect((self.addr, self.port))

    def __del__(self):
        if self.socket is not None:
            self.socket.close()

    def sendRequest(self, msg):
        if self.socket is None:
            raise ConnectionError("RtMessagingClient: Connection is none")
        sendMsg(self.socket, msg)

    def getReply(self):
        if self.socket is None:
            raise ConnectionError("RtMessagingClient: Connection is none")
        msg = recvMsg(self.socket)
        return msg

    def close(self):
        if self.socket is not None:
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
        if useSSL:
            certfile = getCertPath()
            key = getKeyPath()
            self.sslContext = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.sslContext.load_cert_chain(certfile=certfile, keyfile=key)
        self.conn = None

    def __del__(self):
        self.socket.close()

    def getRequest(self):
        """Get the next client request sent over the socket connection.
        Returns: The message as a StructDict data structure
        Exceptions: MessageError, PickleError
        """
        while True:
            try:
                if self.conn is None:
                    # accept a new connection
                    logging.info("RtMessagingServer: waiting for connection ...")
                    self.conn, _ = self.socket.accept()  # Can raise OSError
                    if useSSL:
                        self.conn = self.sslContext.wrap_socket(self.conn, server_side=True)
                    logging.info("RtMessagingServer: connected to {}".format(self.conn.getpeername()))
                # read from the connection
                msg = recvMsg(self.conn)  # Can raise MessageError, PickleError
                return msg
            except ConnectionAbortedError:
                break
            except OSError as err:
                logging.error(repr(err))
                if self.conn is not None:
                    self.conn.close()
                    self.conn = None

    def sendReply(self, msg):
        if self.conn is None:
            raise ConnectionError("RtMessagingServer: Connection is none")
        sendMsg(self.conn, msg)

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        self.socket.close()


def sendMsg(conn, msg):
    data = pickle.dumps(msg)
    hdr = hdrStruct.pack(HDR_MAGIC, msg.type, msg.event_type, len(data))
    conn.sendall(hdr)
    conn.sendall(data)

# header = (magic, msg_type, msg_event_type, msg_size)


def recvMsg(conn):
    """Recieve a formatted message from a socket connection.
    Returns: The message as a StructDict data structure
    Exceptions: MessageError, PickleError
    """
    packed_hdr = recvall(conn, HDR_SIZE)
    (magic, msg_type, msg_event_type, msg_size) = hdrStruct.unpack(packed_hdr)
    if magic != HDR_MAGIC:
        # TODO scan forward if we get out of sync
        raise MessageError("Invalid magic number {}".format(magic))
    # Do some basic validation before reading and unpickling, can throw MessageError
    validateHeader(msg_type, msg_event_type, msg_size)
    data = recvall(conn, msg_size)
    msg = pickle.loads(data)   # can throw PickleError
    return msg


def validateHeader(msg_type, msg_event_type, msg_size):
    if msg_type < MsgType.NoneType or msg_type >= MsgType.MaxType:
        raise MessageError("Invalid type {}".format(msg_type))
    elif msg_event_type < MsgEvent.NoneType or msg_event_type >= MsgEvent.MaxType:
        raise MessageError("Invalid event_type {}".format(msg_event_type))

    if msg_event_type == MsgEvent.RetrieveData:
        if msg_size > MAX_DATA_SIZE:
            raise MessageError("RetrieveData Message size {} exceeded {}".format(msg_size, MAX_DATA_SIZE))
    elif msg_event_type == MsgEvent.TRData:
        if msg_size > MAX_TR_SIZE:
            raise MessageError("TRData Message size {} exceeded {}".format(msg_size, MAX_TR_SIZE))
    elif msg_event_type == MsgEvent.StartSession:
        if msg_size > MAX_SESSION_SIZE:
            raise MessageError("StartSession Message size {} exceeded {}".format(msg_size, MAX_SESSION_SIZE))
    elif msg_size > MAX_META_SIZE:
        raise MessageError("Message size {} exceeded {}".format(msg_size, MAX_META_SIZE))


def recvall(conn, count):
    """Read 'count' bytes from a socket connection. Will loop and continue
    reading until all count bytes are read.
    Returns: byte buffer
    Exceptions: None
    """
    packetByteList = []
    while count:
        # socket.recv no longer can throw InterruptedError as of python 3.5
        packet = conn.recv(count)
        if not packet:
            raise socket.error("connection disconnected")
        packetByteList.append(packet)
        count -= len(packet)
    buf = b''.join(packetByteList)
    return buf


def getCertPath():
    cwd = os.getcwd()
    certfile = os.path.join(cwd, certsDir, sslCertFile)
    if os.path.exists(certfile):
        return certfile
    logging.info("Cert not found in local certs dir: {}".format(certfile))
    paths = ssl.get_default_verify_paths()
    certfile = os.path.join(paths.capath, sslCertFile)
    if not os.path.exists(certfile):
        raise ValidationError("SSL Cert paths not found for {}".format(certfile))
    return certfile


def getKeyPath():
    cwd = os.getcwd()
    keyfile = os.path.join(cwd, certsDir, sslPrivateKey)
    if os.path.exists(keyfile):
        return keyfile
    logging.info("Key not found in local certs dir: {}".format(keyfile))
    paths = ssl.get_default_verify_paths()
    keyfile = os.path.join(os.path.dirname(paths.capath), 'private/', sslPrivateKey)
    if not os.path.exists(keyfile):
        raise ValidationError("SSL Cert paths not found for {}".format(sslPrivateKey))
    return keyfile
