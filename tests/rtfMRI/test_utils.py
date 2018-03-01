#!/usr/bin/env python3

import pytest  # type: ignore
import os
import copy
import time
import random
import pathlib
import scipy.io as sio  # type: ignore
import numpy as np  # type: ignore
from glob import iglob
import rtfMRI.utils as utils  # type: ignore
import rtfMRI.ValidationUtils as vutils  # type: ignore
from rtfMRI.StructDict import StructDict, MatlabStructDict  # type: ignore


@pytest.fixture(scope="module")
def matTestFilename():
    return os.path.join(os.path.dirname(__file__), 'test_input/teststruct.mat')


class TestFindNewestFile:
    TEST_BASE_FILENAME = '/tmp/testdir/file1_20170101T01010'
    NUM_TEST_FILES = 5

    def setup_class(cls):
        # create tmp directory if it doesn't exist
        pathlib.Path('/tmp/testdir/').mkdir(parents=True, exist_ok=True)
        # check if test files already exist, get the count of them
        count_testfiles = sum(1 for _ in iglob(TestFindNewestFile.TEST_BASE_FILENAME + "*"))
        if count_testfiles != TestFindNewestFile.NUM_TEST_FILES:
            # remove any existing testfiles
            for filename in iglob(TestFindNewestFile.TEST_BASE_FILENAME + "*"):
                os.remove(filename)
            # create the correct number of test files
            for i in range(TestFindNewestFile.NUM_TEST_FILES):
                filename = TestFindNewestFile.TEST_BASE_FILENAME + str(i)
                with open(filename, 'w') as fp:
                    fp.write("test file")
                    time.sleep(1)

    def assert_result_matches_filename(self, filename):
        assert filename == (self.TEST_BASE_FILENAME + str(self.NUM_TEST_FILES - 1))

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
        filename = utils.findNewestFile(
            '/tmp/testdir', '/tmp/testdir/file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_pathPartiallyInPattern(self):
        print("Test findNewestFile path partially in pattern:")
        filename = utils.findNewestFile('/tmp', 'testdir/file1_20170101*')
        self.assert_result_matches_filename(filename)

    def test_noMatchingFiles(self):
        print("Test findNewestFile no matching files:")
        filename = utils.findNewestFile('/tmp/testdir/', 'no_such_file')
        assert filename is None


class TestMatlabStructDict:
    @pytest.fixture(scope="class")
    def testStruct(cls, matTestFilename):
        print("## INIT TESTSTRUCT ##")
        teststruct0 = sio.loadmat(matTestFilename)
        testStruct = MatlabStructDict(teststruct0, 'test')
        return testStruct

    def test_loadStruct(self, testStruct):
        print("Test MatlabStructDict:")
        test = copy.deepcopy(testStruct)
        assert test.sub2 == 12
        assert test.top1 == 21
        assert test.top2 == 'hello'
        a = np.array([[[1, 13], [2, 14], [3, 15], [4, 16]],
                      [[5, 17], [6, 18], [7, 19], [8, 20]],
                      [[9, 21], [10, 22], [11, 23], [12, 24]]], dtype=np.uint8)
        assert np.array_equal(test.sub1, a)
        test.test.sub3 = np.array([1, 2, 3])
        assert test['test']['sub3'] is test.sub3
        assert np.array_equal(test.sub3, np.array([1, 2, 3]))
        test.top3 = np.array([[4, 5, 6], [7, 8, 9]])
        assert test['top3'] is test.top3
        assert np.array_equal(
            test.top3, np.array([[4, 5, 6], [7, 8, 9]]))
        test.sub3[0] = 3
        assert np.array_equal(test.sub3, np.array([3, 2, 3]))
        test.sub3 = np.array([10, 20, 30])
        assert np.array_equal(test.sub3, np.array([10, 20, 30]))
        fields = test.fields()
        expected_fields = set(
            ['sub1', 'sub2', 'sub3', 'top1', 'top2', 'top3', 'test'])
        assert fields == expected_fields

    def test_loadMatlabFile(self, testStruct, matTestFilename):
        print("Test LoadMatlabFile")
        struct2 = utils.loadMatFile(matTestFilename)
        assert testStruct.__name__ == struct2.__name__
        res = vutils.compareMatStructs(testStruct, struct2)
        assert vutils.isMeanWithinThreshold(res, 0)


class TestStructDict:
    def test_structDict(self):
        print("Test StructDict:")
        a = StructDict()
        a.top = 1
        a.bottom = 3
        a.sub = StructDict()
        a.sub.left = 'corner'
        assert a.top == 1 and a.bottom == 3 and a.sub.left == 'corner'


class TestCompareArrays:
    A = None
    B = None
    max_deviation = .01

    def setup_class(cls):
        arrayDims = [40, 50, 60]
        A = np.random.random(arrayDims)
        delta = np.random.random(arrayDims) * TestCompareArrays.max_deviation
        B = A + (A * delta)
        TestCompareArrays.A = A
        TestCompareArrays.B = B

    def test_compareArrays(self):
        print("Test compareArrays")
        # import pdb; pdb.set_trace()
        result = vutils.compareArrays(self.B, self.A)
        assert result['mean'] < 2 / 3 * self.max_deviation
        assert result['max'] < self.max_deviation
        return

    def test_areArraysClose(self):
        print("Test areArraysClose")
        max_mean = 2 / 3 * self.max_deviation
        assert vutils.areArraysClose(self.B, self.A, mean_limit=max_mean)
        return


class TestCompareMatStructs:
    A = None
    B = None
    max_deviation = .01

    def setup_class(cls):
        def delta(val):
            return val + (val * random.random() * TestCompareMatStructs.max_deviation)
        A = MatlabStructDict(
            {'sub': MatlabStructDict({})}, 'sub')
        A.str1 = "hello"
        A.a1 = 6.0
        A.sub.a2 = np.array([1, 2, 3, 4, 5], dtype=np.float)
        A.sub.b2 = 7.0
        A.sub.str2 = "world"
        B = MatlabStructDict(
            {'sub': MatlabStructDict({})}, 'sub')
        B.str1 = "hello"
        B.a1 = delta(A.a1)
        B.sub.a2 = delta(A.a2)
        B.sub.b2 = delta(A.b2)
        B.sub.str2 = "world"
        TestCompareMatStructs.A = A
        TestCompareMatStructs.B = B

    def test_compareMatStructs_all_fields(self):
        print("Test compareMatStructs_all_fields")
        result = vutils.compareMatStructs(self.A, self.B)
        means = [result[key]['mean'] for key in result.keys()]
        assert len(means) == 5
        assert all(mean < self.max_deviation for mean in means)

    def test_compareMatStructs_field_subset(self):
        print("Test compareMatStructs_field_subset")
        result = vutils.compareMatStructs(self.A, self.B, ['a2', 'str1'])
        means = [result[key]['mean'] for key in result.keys()]
        assert len(means) == 2
        assert all(mean < self.max_deviation for mean in means)

    def test_isMeanWithinThreshold(self):
        a = {'val1': {'mean': .1, 'max': .2},
             'val2': {'mean': .05, 'max': .075}}
        assert vutils.isMeanWithinThreshold(a, .11)
        assert not vutils.isMeanWithinThreshold(a, .09)


class TestCompareMatFiles:
    def test_compareMatFiles(self, matTestFilename):
        res = vutils.compareMatFiles(matTestFilename, matTestFilename)
        assert vutils.isMeanWithinThreshold(res, 0)


class TestPearsonsMeanCorr:
    def test_pearsonsMeanCorr(self):
        n1 = np.array([[1, 2, 3, 4, 5],
                       [np.nan, np.nan, np.nan, np.nan, np.nan]])
        n2 = np.array([[1.1, 2.1, 3.2, 4.1, 5.05],
                       [np.nan, np.nan, np.nan, np.nan, np.nan]])
        n1t = np.transpose(n1)
        n2t = np.transpose(n2)
        res = vutils.pearsons_mean_corr(n1t, n2t)
        assert res > 0.999


if __name__ == "__main__":
    print("PYTEST MAIN:")
    pytest.main()
