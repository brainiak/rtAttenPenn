#!/usr/bin/env python3

import unittest
import os, time, pathlib
from glob import iglob
import FindNewestFile as fn

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
        filename = fn.findNewestFile('/tmp/testdir', 'file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_emptyPath(self):
        filename = fn.findNewestFile('', '/tmp/testdir/file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_pathInPattern(self):
        filename = fn.findNewestFile('/tmp/testdir', '/tmp/testdir/file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_pathPartiallyInPattern(self):
        filename = fn.findNewestFile('/tmp', 'testdir/file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_noMatchingFiles(self):
        filename = fn.findNewestFile('/tmp/testdir/', 'no_such_file')
        self.assertEqual(filename, '')

    def assert_result_matches_filename(self, filename):
        self.assertEqual(filename, TEST_BASE_FILENAME + str(NUM_TEST_FILES-1))
