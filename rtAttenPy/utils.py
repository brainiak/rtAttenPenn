#!/usr/bin/env python3

import os
import glob
import re
import numpy as np


def findNewestFile(filepath, filepattern):
    '''Find newest file according to filesystem creation time
        and return the filename.
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
