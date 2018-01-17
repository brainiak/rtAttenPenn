import unittest
import threading
from rtfMRI.MsgTypes import MsgType, MsgEvent
from rtfMRI.Messaging import Message, RtMessagingServer, RtMessagingClient

class Test_Messaging(unittest.TestCase):
    def setUp(self):
        self.server = RtMessagingServer(5501)
        def serveRequests():
            while True:
                req = self.server.getRequest()
                if req.type == MsgType.Shutdown:
                    break
                reply = Message()
                reply.id = req.id
                reply.type = MsgType.Reply
                reply.event_type = MsgEvent.Success
                self.server.sendReply(reply)
            self.server.close()
        self.server_thread = threading.Thread(name='server', target=serveRequests)
        self.server_thread.setDaemon(True)
        self.server_thread.start()
    def tearDown(self):
        self.server.close()
    def test_sendMessages(self):
        client = RtMessagingClient('localhost', 5501)
        msg = Message()
        msg.id = 1
        msg.type = MsgType.Command
        msg.event_type = MsgEvent.TrialData
        msg.fields.a = 10
        msg.data = [1, 2, 3, 4, 5]
        client.sendRequest(msg)
        reply = client.getReply()
        self.assertTrue(reply.type == MsgType.Reply)
        self.assertTrue(reply.event_type == MsgEvent.Success)
        client.close()
        # Reconnect client
        client = RtMessagingClient('localhost', 5501)
        client.sendRequest(msg)
        reply = client.getReply()
        self.assertTrue(reply.type == MsgType.Reply)
        self.assertTrue(reply.event_type == MsgEvent.Success)
        msg.type = MsgType.Shutdown
        client.sendRequest(msg)
        self.server_thread.join()
        client.close()

if __name__ == '__main__':
    unittest.main()
