#!/usr/bin/env python3

import os
import glob
import re
import numpy as np


def findNewestFile(filepath, filepattern):
    '''Find newest file matching pattern according to filesystem creation time.
       Return the filename
    '''
    full_path_pattern = ''
    if os.path.basename(filepattern) == filepath:
        # filepattern has the full path in it already
        full_path_pattern = filepattern
    elif os.path.basename(filepattern) == '':
        # filepattern doesn't have the file path in it yet
        # concatenate file path to filepattern
        full_path_pattern = os.path.join(filepath, filepattern)
    else:
        # base of filepattern and filepath don't seem to match, raise error?
        # for now concatenate them also
        full_path_pattern = os.path.join(filepath, filepattern)

    try:
        return max(glob.iglob(full_path_pattern), key=os.path.getctime)
    except ValueError:
        return ''

# Data loaded from matlab is as a structured array. But it's not easy to add
#  new fields to a structured array, so convert it to a dictionary for easier use
def convertStructuredArrayToDict(sArray):
    '''Convert a NumPy structured array to a dictionary. Return the dictionary'''
    rvDict = dict()
    for key in sArray.dtype.names:
        try:
            val = sArray[key]
            # Check for and flatten arrays with only one element in them
            if isinstance(val, np.ndarray) and val.shape == (1, 1):
                val = val[0][0]
            rvDict[key] = val
        except KeyError:
            pass
    return rvDict

# Class to make it easier to access fields in matlab structs loaded into python
class MatlabStructDict(dict):
    '''Subclass dictionary so that elements can be accessed either as dict['key']
        of dict.key. If elements are of type NumPy structured arrays, convert
        them to dictionaries and then to MatlabStructDict also.
    '''
    def __init__(self, dictionary, name=None):
        # name is used to identify a special field whose elements should be considered
        #  as first level elements. i.e. name=patterns, then data.patterns.field
        #  will return the same as data.field
        self.__name__ = name
        super().__init__(dictionary)
        # For any numpy arrays that are structured arrays, convert the to MatlabStructDict
        for key in self.keys():
            try:
                # structured arrays will have a non-zero set self[key].dtype.names
                if isinstance(self[key], np.ndarray) and len(self[key].dtype.names) > 0:
                    self[key] = MatlabStructDict(convertStructuredArrayToDict(self[key]))
            except TypeError:
                pass

    def __getattr__(self, key):
        '''Implement get attribute so that for x=data.field can be used'''
        struct = self
        # if the key isn't found at the top level, check if it is a sub-field of
        # the special 'name' field
        if key not in self.keys() and self.__name__ in self.keys():
            struct = self[self.__name__]
        try:
            val = struct[key]
        except KeyError:
            val = None
        # flatten numpy arrays
        while isinstance(val, np.ndarray) and val.shape == (1, 1):
            val = val[0][0]
        return val

    def __setattr__(self, key, val):
        '''Implement set attribute for dictionary so that form data.field=x can be used'''
        # check for special __fields__ and do default handling
        if re.match('__.*__', key):
            super().__setattr__(key, val)
            return
        # make sure we aren't setting something that should go in the special name field
        if self.__name__ is not None:
            try:
                assert key not in self[self.__name__].keys()
            except AttributeError:
                pass
        # pack ints in 2d array [[int]] as matlab does
        if isinstance(val, int):
            field_type = None
            if val in range(256):
                field_type = np.uint8
            self[key] = np.array([[val]], dtype=field_type)
        else:
            self[key] = val

    def fields(self):
        '''list out all fields including the subfields of the special 'name' field'''
        struct_fields = ()
        try:
            struct = self[self.__name__]
            if isinstance(struct, np.ndarray):
                struct_fields = struct.dtype.names
        except KeyError:
            pass
        s = set().union(self.keys(), struct_fields)
        # TODO - remove fields with __*__ pattern
        return s

def compareArrays(A: np.ndarray, B: np.ndarray) -> dict:
    """Compute element-wise percent difference between A and B
       Return the mean, max, stddev, histocounts, histobins in a Dict
    """
    assert isinstance(A, np.ndarray) and isinstance(B, np.ndarray), "assert numpy arrays failed"
    assert A.size == B.size, "assert equal size arrays failed"
    if A.shape != B.shape:
        if A.shape[-1] == 1:
            A = A.reshape(A.shape[:-1])
        if B.shape[-1] == 1:
            B = B.reshape(B.shape[:-1])
        assert len(A.shape) == len(B.shape), "assert same number of dimensions"
        assert A.shape[::-1] == B.shape, "assert similar shape arrays"
        A = A.reshape(B.shape)
    diff = abs(A - B) / B
    histobins = [0, 0.005, .01, .02, .03, .04, .05, .06, .07, .09, .1, 1]
    histocounts, histobins = np.histogram(diff, histobins)
    result = {'min': np.min(diff), 'max': np.max(diff),
              'mean': np.mean(diff), 'stddev': np.std(diff),
              'histocounts': histocounts, 'histobins': histobins}
    return result

def areArraysClose(A: np.ndarray, B: np.ndarray, mean_limit=.01, stddev_limit=1.0) -> bool:
    '''Compare to arrays element-wise and compute the percent difference.
       Return True if the mean and stddev are withing the supplied limits.
       Default limits: {mean: .01, stddev: 1.0} , i.e. no stddev limit by default
    '''
    res = compareArrays(A, B)
    if res['mean'] > mean_limit:
        return False
    if res['stddev'] > stddev_limit:
        return False
    return True
