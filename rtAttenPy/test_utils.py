#!/usr/bin/env python3

import unittest
import os, time, random, pathlib
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

    def assert_result_matches_filename(self, filename):
        self.assertEqual(filename, TEST_BASE_FILENAME + str(NUM_TEST_FILES-1))

    def test_normalCase(self):
        print("Test findNewestFile normal case:")
        filename = utils.findNewestFile('/tmp/testdir', 'file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_emptyPath(self):
        print("Test findNewestFile empty path:")
        filename = utils.findNewestFile('', '/tmp/testdir/file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_pathInPattern(self):
        print("Test findNewestFile path embedded in pattern:")
        filename = utils.findNewestFile('/tmp/testdir', '/tmp/testdir/file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_pathPartiallyInPattern(self):
        print("Test findNewestFile path partially in pattern:")
        filename = utils.findNewestFile('/tmp', 'testdir/file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_noMatchingFiles(self):
        print("Test findNewestFile no matching files:")
        filename = utils.findNewestFile('/tmp/testdir/', 'no_such_file')
        self.assertEqual(filename, None)


#import matlab.engine
import scipy.io as sio
import numpy as np
import copy

matTestFilename = os.path.join(os.path.dirname(utils.__file__),'test_input/teststruct.mat')

class TestMatlabStructDict(unittest.TestCase):
    def setUp(self):
        # matlab code to generate test file
        # self.matlab = matlab.engine.start_matlab()
        # test.sub1 = [1 2 3 4; 5 6 7 8; 9 10 11 12]
        # test.sub1(:,:,2) = [13 14 15 16; 17 18 19 20; 21 22 23 24]
        # test.sub2 = 12
        # top1 = 21
        # top2 =  'hello'
        # save('teststruct.mat', 'test', 'top1', 'top2')
        teststruct0 = sio.loadmat(matTestFilename)
        self.testStruct = utils.MatlabStructDict(teststruct0, 'test')
        pass
    def tearDown(self):
        # self.matlab.quit()
        pass
    def test_loadStruct(self):
        print("Test MatlabStructDict:")
        test = self.testStruct.copy()
        self.assertEqual(test.sub2, 12)
        self.assertEqual(test.top1, 21)
        self.assertEqual(test.top2, 'hello')
        a = np.array([[[1, 13], [2, 14], [3, 15], [4, 16]],
                      [[5, 17], [6, 18], [7, 19], [8, 20]],
                      [[9, 21], [10, 22], [11, 23], [12, 24]]], dtype=np.uint8)
        self.assertTrue(np.array_equal(test.sub1, a))
        test.test.sub3 = np.array([1, 2, 3])
        self.assertTrue(test['test']['sub3'] is test.sub3)
        self.assertTrue(np.array_equal(test.sub3, np.array([1, 2, 3])))
        test.top3 = np.array([[4, 5, 6], [7, 8, 9]])
        self.assertTrue(test['top3'] is test.top3)
        self.assertTrue(np.array_equal(test.top3, np.array([[4, 5, 6], [7, 8, 9]])))
        test.sub3[0] = 3
        self.assertTrue(np.array_equal(test.sub3, np.array([3, 2, 3])))
        test.sub3 = np.array([10, 20, 30])
        self.assertTrue(np.array_equal(test.sub3, np.array([10, 20, 30])))
        fields = test.fields()
        expected_fields = set(['sub1', 'sub2', 'sub3', 'top1', 'top2', 'top3', 'test'])
        self.assertTrue(fields == expected_fields)
    def test_loadMatlabFile(self):
        print("Test LoadMatlabFile")
        struct2 = utils.loadMatFile(matTestFilename)
        self.assertTrue(self.testStruct.__name__ == struct2.__name__)
        res = utils.compareMatStructs(self.testStruct, struct2)
        self.assertTrue(utils.isMeanWithinThreshold(res, 0))

class TestStructDict(unittest.TestCase):
    def setUp(self):
        pass
    def test_structDict(self):
        print("Test StructDict:")
        a = utils.StructDict()
        a.top = 1
        a.bottom = 3
        a.sub = utils.StructDict()
        a.sub.left = 'corner'
        self.assertTrue(a.top == 1 and a.bottom == 3 and a.sub.left == 'corner')

class TestCompareArrays(unittest.TestCase):
    def setUp(self):
        self.max_deviation = .01
        arrayDims = [40, 50, 60]
        self.A = np.random.random(arrayDims)
        delta = np.random.random(arrayDims) * self.max_deviation
        self.B = self.A + (self.A * delta)
        pass
    def tearDown(self):
        pass
    def test_compareArrays(self):
        print("Test compareArrays")
        result = utils.compareArrays(self.B, self.A)
        self.assertTrue(result['mean'] < 2/3 * self.max_deviation)
        self.assertTrue(result['max'] < self.max_deviation)
        return
    def test_areArraysClose(self):
        print("Test areArraysClose")
        max_mean = 2/3 * self.max_deviation
        self.assertTrue(utils.areArraysClose(self.B, self.A, mean_limit = max_mean))
        return

class TestCompareMatStructs(unittest.TestCase):
    def setUp(self):
        self.max_deviation = .01
        def delta(val):
            return val + (val * random.random() * self.max_deviation)
        self.A = utils.MatlabStructDict({'sub': utils.MatlabStructDict({})}, 'sub')
        self.A.str1 = "hello"
        self.A.a1 = 6.0
        self.A.sub.a2 = np.array([1, 2, 3, 4, 5], dtype=np.float)
        self.A.sub.b2 = 7.0
        self.A.sub.str2 = "world"
        self.B = utils.MatlabStructDict({'sub': utils.MatlabStructDict({})}, 'sub')
        self.B.str1 = "hello"
        self.B.a1 = delta(self.A.a1)
        self.B.sub.a2 = delta(self.A.a2)
        self.B.sub.b2 = delta(self.A.b2)
        self.B.sub.str2 = "world"
    def tearDown(self):
        pass
    def test_compareMatStructs_all_fields(self):
        print("Test compareMatStructs_all_fields")
        result = utils.compareMatStructs(self.A, self.B)
        means = [result[key]['mean'] for key in result.keys()]
        self.assertTrue(len(means)==5)
        self.assertTrue(all(mean < self.max_deviation for mean in means))
    def test_compareMatStructs_field_subset(self):
        print("Test compareMatStructs_field_subset")
        result = utils.compareMatStructs(self.A, self.B, ['a2','str1'])
        means = [result[key]['mean'] for key in result.keys()]
        self.assertTrue(len(means)==2)
        self.assertTrue(all(mean < self.max_deviation for mean in means))
    def test_isMeanWithinThreshold(self):
        a = {'val1': {'mean': .1, 'max': .2}, 'val2': {'mean': .05, 'max': .075}}
        self.assertTrue(utils.isMeanWithinThreshold(a, .11))
        self.assertFalse(utils.isMeanWithinThreshold(a, .09))


class TestCompareMatFiles(unittest.TestCase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    def test_compareMatFiles(self):
        res = utils.compareMatFiles(matTestFilename, matTestFilename)
        self.assertTrue(utils.isMeanWithinThreshold(res, 0))

if __name__ == "__main__":
    unittest.main()
