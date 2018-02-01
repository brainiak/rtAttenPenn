"""
Utils - various utilites for rtfMRI
"""

import os
import glob
import numpy as np  # type: ignore
import scipy.io as sio  # type: ignore
from .StructDict import MatlabStructDict, isStructuredArray


class TooManySubStructsError(ValueError):
    pass


def loadMatFile(filename: str) -> MatlabStructDict:
    '''Load matlab data file and convert it to a MatlabStructDict object for
       easier python access. Expect only one substructure array, and use that
       one as the name variable in MatlabStructDict.
       Return the MatlabStructDict object
    '''
    if not os.path.isfile(filename):
        raise FileNotFoundError("File \'{}\' not found".format(filename))
    top_struct = sio.loadmat(filename)
    substruct_names = [key for key in top_struct.keys() if isStructuredArray(top_struct[key])]
    if len(substruct_names) > 1:
        # Currently we only support one sub structured array
        raise TooManySubStructsError(
            "Too many substructs: {}".format(substruct_names))
    substruct_name = substruct_names[0] if len(substruct_names) > 0 else None
    matstruct = MatlabStructDict(top_struct, substruct_name)
    return matstruct


def find(A: np.ndarray) -> np.ndarray:
    '''Find nonzero elements of A in flat "C" row-major indexing order
       but sorted as in "F" column indexing order'''
    # find indices of non-zero elements in roi
    inds = np.nonzero(A)
    dims = A.shape
    # First convert to Matlab column-order raveled indicies in order to sort
    #   the indicies to match the order the data appears in the p.raw matrix
    indsMatRavel = np.ravel_multi_index(inds, dims, order='F')
    indsMatRavel.sort()
    # convert back to python raveled indices
    indsMat = np.unravel_index(indsMatRavel, dims, order='F')
    resInds = np.ravel_multi_index(indsMat, dims, order='C')
    return resInds


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


def flatten_1Ds(M):
    if 1 in M.shape:
        newShape = [x for x in M.shape if x > 1]
        M = M.reshape(newShape)
    return M


'''
import inspect  # type: ignore
def xassert(bool_val, message):
    print("in assert")
    if bool_val is False:
        frame = inspect.currentframe()
        xstr = "File: {}, Line: {} AssertionFailed: {}"\
            .format(os.path.basename(frame.f_code.co_filename),
                    frame.f_lineno, message)
        assert False, xstr
'''
