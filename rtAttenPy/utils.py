#!/usr/bin/env python3

import os
import glob
import re
import numpy as np
import numbers
import scipy.io as sio


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
        return None

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


class StructDict(dict):
    '''Subclass dictionary so that elements can be accessed either as dict['key'] or dict.key.'''
    def __getattr__(self, key):
        '''Implement get attribute so that experssions like data.field can be used'''
        try:
            val = self[key]
        except KeyError:
            val = None
        return val

    def __setattr__(self, key, val):
        '''Implement set attribute for dictionary so that form data.field=x can be used'''
        self[key] = val


# Class to make it easier to access fields in matlab structs loaded into python
class MatlabStructDict(StructDict):
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
        # if the key isn't found at the top level, check if it is a sub-field of
        # the special 'name' field so we can set the value there
        struct = self
        if key not in self.keys() and self.__name__ in self.keys():
            if key in self[self.__name__].keys():
                struct = self[self.__name__]

        # pack ints in 2d array [[int]] as matlab does
        if isinstance(val, int):
            field_type = None
            if val in range(256):
                field_type = np.uint8
            struct[key] = np.array([[val]], dtype=field_type)
        else:
            struct[key] = val

    def copy(self):
        return MatlabStructDict(super().copy(), self.__name__)

    def fields(self):
        '''list out all fields including the subfields of the special 'name' field'''
        struct_fields = ()
        try:
            struct = self[self.__name__]
            if isinstance(struct, MatlabStructDict):
                struct_fields = struct.keys()
        except KeyError:
            pass
        allfields = set().union(self.keys(), struct_fields)
        s = set([field for field in allfields if not re.match('__.*__', field)])
        return s

# Globals
numpyAllNumCodes = np.typecodes['AllFloat'] + np.typecodes['AllInteger']
StatsEqual = {'mean': 0, 'count': 1, 'min': 0, 'max': 0, 'stddev': 0, 'histocounts': None, 'histobins': None, 'histopct': None}
StatsNotEqual = {'mean': 1, 'count': 1, 'min': 1, 'max': 1, 'stddev': 1, 'histocounts': None, 'histobins': None, 'histopct': None}

def compareArrays(A: np.ndarray, B: np.ndarray) -> dict:
    """Compute element-wise percent difference between A and B
       Return the mean, max, stddev, histocounts, histobins in a Dict
    """
    assert isinstance(A, np.ndarray) and isinstance(B, np.ndarray), "compareArrays: assert expecting ndarrays got {} {}".format(type(A), type(B))
    assert A.size == B.size, "compareArrays: assert equal size arrays failed"
    if A.shape != B.shape:
        def flatten_1Ds(M):
            if 1 in M.shape:
                newShape = [x for x in M.shape if x > 1]
                M = M.reshape(newShape)
        flatten_1Ds(A)
        flatten_1Ds(B)
        assert len(A.shape) == len(B.shape), "compareArrays: expecting same num dimension but got {} {}".format(len(A.shape), len(B.shape))
        if A.shape != B.shape:
            # maybe the shape dimensions are reversed
            assert A.shape[::-1] == B.shape, "compareArrays: expecting similar shape arrays got {} {}".format(A.shape, B.shape)
            A = A.reshape(B.shape)
        assert A.shape == B.shape, "compareArrays: expecting arrays to have the same shape got {} {}".format(A.shape, B.shape)
    if A.dtype.kind not in numpyAllNumCodes:
        # Not a numeric array
        return StatsEqual if np.array_equal(A, B) else StatsNotEqual
    # Numeric arrays
    diff = abs((A / B) - 1)
    diff = np.nan_to_num(diff)
    histobins = [0, 0.005, .01, .02, .03, .04, .05, .06, .07, .09, .1, 1]
    histocounts, histobins = np.histogram(diff, histobins)
    result = {'mean': np.mean(diff), 'count': A.size,
              'min': np.min(diff), 'max': np.max(diff), 'stddev': np.std(diff),
              'histocounts': histocounts, 'histobins': histobins,
               'histopct': histocounts / A.size * 100}
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

class StructureMismatchError(ValueError):
    pass

def compareMatStructs(A: MatlabStructDict, B: MatlabStructDict, field_list=None) -> dict:
    '''For each field, not like __*__, walk the fields and compare the values.
       If a field is missing from one of the structs raise an exception.
       If field_list is supplied, then only compare those fields.
       Return a dict with {fieldname: stat_results}.'''
    result = {}
    if field_list is None:
        field_list = A.fields()
    fieldSet = set(field_list)
    ASet = set(A.fields())
    BSet = set(B.fields())
    if not fieldSet <= ASet or not fieldSet <= BSet:
        raise StructureMismatchError("missing fields: {}, {}".format(ASet-fieldSet, BSet-fieldSet))

    for key in field_list:
        valA = getattr(A, key)
        valB = getattr(B, key)
        if type(valA) != type(valB):
            raise StructureMismatchError("field {} has different types {}, {}".format(key, type(valA), type(valB)))

        if isinstance(valA, MatlabStructDict):
            stats = compareMatStructs(valA, valB)
            for subkey, subresult in stats.items():
                result[subkey] = subresult
        elif isinstance(valA, np.ndarray):
            stats = compareArrays(valA, valB)
            result[key] = stats
        else:
            diff = 0
            if isinstance(valA, numbers.Number):
                diff = abs((valA / valB) - 1)
            else:
                try:
                    diff = 0 if (valA == valB) else 1
                except ValueError:
                    print("Error comparing {} {} or type {}".format(valA, valB, type(valA)))
                    raise
            stats = {'mean': diff, 'count': 1, 'min': diff, 'max': diff, 'stddev': 0, 'histocounts': None, 'histobins': None, 'histopct': None}
            result[key] = stats
    return result

def isMeanWithinThreshold(cmpStats: dict, threshold: float) -> bool:
    '''Examine all mean stats in dictionary and compare the the threshold value'''
    means = [value['mean'] for key, value in cmpStats.items()]
    assert len(means) == len(cmpStats.keys()), "isMeanWithinThreshold: assertion failed, length means mismatch {} {}".format(len(means), len(cmpStats.keys()))
    return all(mean <= threshold for mean in means)

class TooManySubStructsError(ValueError):
    pass

def isStructuredArray(var) -> bool:
    return True if isinstance(var, np.ndarray) and (var.dtype.names is not None) and len(var.dtype.names) > 0 else False

def loadMatFile(filename: str) -> MatlabStructDict:
    '''Load matlab data file and convert it to a MatlabStructDict object for
       easier python access. Expect only one substructure array, and use that
       one as the name variable in MatlabStructDict.
       Return the MatlabStructDict object
    '''
    top_struct = sio.loadmat(filename)
    substruct_names = [key for key in top_struct.keys() if isStructuredArray(top_struct[key])]
    if len(substruct_names) > 1:
        # Currently we only support one sub structured array
        raise TooManySubStructsError("Too many substructs: {}".format(substruct_names))
    substruct_name = substruct_names[0] if len(substruct_names) > 0 else None
    matstruct = MatlabStructDict(top_struct, substruct_name)
    return matstruct

def compareMatFiles(filename1: str, filename2: str) -> dict:
    '''Load both matlab files and call compareMatStructs.
       Inspect the resulting stats_result to see if any mean difference is beyond
       some threshold. Also print out the stats results.
       Return the result stats.
    '''
    matstruct1 = loadMatFile(filename1)
    matstruct2 = loadMatFile(filename2)
    if matstruct1.__name__ != matstruct2.__name__:
        raise StructureMismatchError("Substructures don't match A {}, B {}".format(matstruct1.__name__, matstruct2.__name__))
    result = compareMatStructs(matstruct1, matstruct2)
    return result


def find(A: np.ndarray):
    '''Find nonzero elements of A in flat "C" row-major indexing order
       but sorted as in "F" column indexing order'''
    # find indices of non-zero elements in roi
    inds = np.nonzero(A)
    dims = A.shape
    # We need to first convert to Matlab column order raveled indicies in order to
    #  sort the indicies in that order (the order the data appears in the p.raw matrix)
    indsMatRavel = np.ravel_multi_index(inds, dims, order='F')
    indsMatRavel.sort()
    # convert back to python raveled indices
    indsMat = np.unravel_index(indsMatRavel, dims, order='F')
    resInds = np.ravel_multi_index(indsMat, dims, order='C')
    return resInds


import inspect
def xassert(bool_val, message):
    print("in assert")
    if bool_val is False:
        frame = inspect.currentframe()
        xstr = "File: {}, Line: {} AssertionFailed: {}".format(os.path.basename(frame.f_code.co_filename), frame.f_lineno, message)
        assert False, xstr
