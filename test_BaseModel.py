import unittest
import ClientMain


class Test_BaseModel(unittest.TestCase):
    def test_baseModel(self):
        print("test_baseModel")
        client_args = ['ClientMain.py', '-l']
        result = ClientMain.client_main(client_args)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
