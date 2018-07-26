import socket
import time
import serial
import struct

USE_MULTICAST = False
MULTICAST_ADDR = "231.2.3.4"
MULTICAST_PORT = 5300
MsgFormat = struct.Struct("!d")


def TTLPulseServer():
    while True:
        try:
            # Open the USB0 port and listen for TTL Pulses
            ser_conn = serial.Serial('/dev/ttyUSB0', 9600)

            # Open UDP Socket for Multicast (or Broadcast)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            if USE_MULTICAST:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            else:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            while True:
                # When receive a pulse, send out a UDP broadcast
                pulse = ser_conn.read()
                valStr = pulse.decode("utf-8")
                val = int(valStr)
                assert 0 <= val <= 9
                timestamp = time.time()
                msg = MsgFormat.pack(timestamp)
                if USE_MULTICAST:
                    sock.sendto(msg, (MULTICAST_ADDR, MULTICAST_PORT))
                else:
                    sock.sendto(msg, ('<broadcast>', MULTICAST_PORT))
                print("Send timestamp {}".format(timestamp))
                time.sleep(1)
            sock.close()

        except serial.SerialException as err:
            # sleep and try again
            time.sleep(30)
            continue
        # except OSError as err:
        #     # likely a socket error
        ser_conn.close()


def TTLPulseClient():
    # sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
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
        sock.bind(("", MULTICAST_PORT))

    while True:
        print("listen")
        data, addr = sock.recvfrom(256)
        msg = MsgFormat.unpack(data)
        timestamp = msg[0]
        print("Pulse: {} {}".format(timestamp, time.time() - timestamp))
        # Add a yield here to return the timestamp
        # Or maybe have the global variable with the timestamp here
        # Depends on if we want to be notified.
        # Could use thread events
        # We'll want to wrap these in threads? No


if __name__ == '__main__':
    TTLPulseServer()
