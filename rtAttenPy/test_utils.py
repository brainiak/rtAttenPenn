#!/usr/bin/env python3

import unittest
import os, time, pathlib
from rtAttenPy import utils
from glob import iglob

TEST_BASE_FILENAME = '/tmp/testdir/file1_20170101T01010'
NUM_TEST_FILES = 5

class TestFindNewestFile(unittest.TestCase):
    def setUp(self):
        # create tmp directory if it doesn't exist
        pathlib.Path('/tmp/testdir/').mkdir(parents=True, exist_ok=True)
        # check if test files already exist, get the count of them
        count_testfiles = sum(1 for _ in iglob(TEST_BASE_FILENAME + "*"))
        if count_testfiles != NUM_TEST_FILES:
            # remove any existing testfiles
            for filename in iglob(TEST_BASE_FILENAME + "*"):
                os.remove(filename)
            # create the correct number of test files
            for i in range(NUM_TEST_FILES):
                filename = TEST_BASE_FILENAME + str(i)
                with open(filename, 'w') as fp:
                    fp.write("test file")
                    time.sleep(1)

    def tearDown(self):
        pass

    def test_normalCase(self):
        filename = utils.findNewestFile('/tmp/testdir', 'file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_emptyPath(self):
        filename = utils.findNewestFile('', '/tmp/testdir/file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_pathInPattern(self):
        filename = utils.findNewestFile('/tmp/testdir', '/tmp/testdir/file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_pathPartiallyInPattern(self):
        filename = utils.findNewestFile('/tmp', 'testdir/file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_noMatchingFiles(self):
        filename = utils.findNewestFile('/tmp/testdir/', 'no_such_file')
        self.assertEqual(filename, '')

    def assert_result_matches_filename(self, filename):
        self.assertEqual(filename, TEST_BASE_FILENAME + str(NUM_TEST_FILES-1))


#import matlab.engine
import scipy.io as sio
import numpy as np

class TestMatlabStructDict(unittest.TestCase):
    def setUp(self):
        # matlab code to generate test file
        # self.matlab = matlab.engine.start_matlab()
        # test.a = [1 2 3 4; 5 6 7 8; 9 10 11 12]
        # test.a(:,:,2) = [13 14 15 16; 17 18 19 20; 21 22 23 24]
        # test.b = 12
        # c = 21
        # d =  'hello'
        # save('teststruct.mat', 'test', 'c', 'd')
        pass
    def tearDown(self):
        # self.matlab.quit()
        pass
    def test_loadStruct(self):
        teststruct = sio.loadmat('teststruct.mat')
        test = utils.MatlabStructDict(teststruct, 'test')
        self.assertEqual(test.b, 12)
        self.assertEqual(test.c, 21)
        self.assertEqual(test.d, 'hello')
        a = np.array([[[1, 13], [2, 14], [3, 15], [4, 16]],
                      [[5, 17], [6, 18], [7, 19], [8, 20]],
                      [[9, 21], [10, 22], [11, 23], [12, 24]]], dtype=np.uint8)
        self.assertEqual(np.array_equal(test.a, a), True)
