#!/usr/bin/env python3

import os
import glob
import re
import numpy as np


def findNewestFile(filepath, filepattern):
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

class MatlabStructDict(dict):
    def __init__(self, dictionary, name=None):
        self.__name__ = name
        super().__init__(dictionary)

    def __getattr__(self, key):
        struct = self
        if key not in self.keys() and self.__name__ in self.keys():
            struct = self[self.__name__]
        try:
            val = struct[key]
        except KeyError:
            val = None
        if isinstance(val, np.ndarray) and val.shape == (1, 1):
            val = val[0][0]
        return val

    def __setattr__(self, key, val):
        if re.match('__.*__', key):
            super().__setattr__(key, val)
            return
        field_type = None
        if isinstance(val, int) and val in range(256):
            field_type = np.uint8
        self[key] = np.array([[val]], dtype=field_type)
