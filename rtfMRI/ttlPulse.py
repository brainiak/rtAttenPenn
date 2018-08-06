import socket
import time
import serial
import struct
import threading
import argparse

USE_MULTICAST = False
MULTICAST_ADDR = "231.2.3.4"
MULTICAST_PORT = 5300
MsgFormat = struct.Struct("!d")


def TTLPulseServer(serialDevice, serialBaud):
    while True:
        try:
            serialConn = None
            if serialDevice is not None:
                # Open the USB0 port and listen for TTL Pulses
                serialConn = serial.Serial(serialDevice, serialBaud)

            # Open UDP Socket for Multicast (or Broadcast)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            if USE_MULTICAST:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            else:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            pulseCnt = 0
            while True:
                # When receive a pulse, send out a UDP broadcast
                if serialConn is not None:
                    pulse = serialConn.read()
                    pulseStr = pulse.decode("utf-8")
                    pulseCnt = int(pulseStr)
                    assert 0 <= pulseCnt <= 9
                else:
                    time.sleep(1)
                    pulseCnt = (pulseCnt + 1) % 10

                timestamp = time.time()
                msg = MsgFormat.pack(timestamp)
                if USE_MULTICAST:
                    sock.sendto(msg, (MULTICAST_ADDR, MULTICAST_PORT))
                else:
                    sock.sendto(msg, ('<broadcast>', MULTICAST_PORT))
                # print("Send timestamp {}".format(timestamp))

            sock.close()

        except serial.SerialException as err:
            # sleep and try again
            time.sleep(30)
            continue
        # except OSError as err:
        #     # likely a socket error
        serialConn.close()


class TTLPulseClient():
    def __init__(self):
        # Class attributes
        self.sock = None
        self.timestamp = 0
        self.resetThread = None
        self.listenThread = None
        self.PulseNotify = None
        self.shouldExit = False
        self.maxTRTime = 2  # 2 seconds max TR time by default

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        if USE_MULTICAST:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            sock.bind((MULTICAST_ADDR, MULTICAST_PORT))
            # Set more multicast options
            intf = socket.gethostbyname(socket.gethostname())
            sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(intf))
            sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP,
                            socket.inet_aton(MULTICAST_ADDR) + socket.inet_aton(intf))
        else:
            # Use Broadcast
            sock.bind(("", MULTICAST_PORT))
        self.sock = sock
        # start reset timestamp thread
        self.resetThread = threading.Thread(target=self.resetTimestampThread)
        self.resetThread.setDaemon(True)
        self.resetThread.start()
        # start listen thread
        self.PulseNotify = threading.Event()
        self.listenThread = threading.Thread(target=self.listenTTLThread)
        self.listenThread.setDaemon(True)
        self.listenThread.start()

    def __del__(self):
        self.close()

    def close(self):
        self.shouldExit = True
        if self.sock is not None:
            self.sock.close()
            self.sock = None
        if self.listenThread is not None:
            self.listenThread.join()
            self.listenThread = None
        if self.resetThread is not None:
            self.resetThread.join()
            self.resetThread = None

    def getTimestamp(self):
        return self.timestamp

    def getPulseEvent(self):
        return self.PulseNotify

    def setMaxTRTime(self, maxTR):
        self.maxTRTime = maxTR

    def resetTimestampThread(self):
        prevTimestamp = self.timestamp
        while not self.shouldExit:
            # sleep 1.5 times the max TR time
            time.sleep(self.maxTRTime * 1.5)
            if self.timestamp == prevTimestamp:
                # print("Client reset timestamp")
                self.timestamp = 0
            prevTimestamp = self.timestamp

    def listenTTLThread(self):
        while not self.shouldExit:
            # Clear the PulseNotify Event so calling threads will wait for time signal
            self.PulseNotify.clear()
            try:
                data, addr = self.sock.recvfrom(256)
            except OSError as err:
                print("ListenTTLThread drop connection")
            msg = MsgFormat.unpack(data)
            self.timestamp = msg[0]
            # Set the PulseNotify Event to wake up calling threads
            self.PulseNotify.set()
            # print("Pulse: {} {}".format(self.timestamp, time.time() - self.timestamp))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', action="store", dest="serialDev")
    parser.add_argument('-b', action="store", dest="serialBaud")
    args = parser.parse_args()
    if args.serialDev is None:
        print("No serial device specified, sending pulse every second")
        TTLPulseServer(None, 0)
    else:
        if args.serialBaud is None:
            args.serialBaud = 9600
        print("Listen on device {} {}".format(args.serialDev, args.serialBaud))
        TTLPulseServer(args.serialDev, args.serialBaud)
