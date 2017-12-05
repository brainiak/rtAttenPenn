#!python
# cython: embedsignature=True, binding=True, boundscheck=False, wraparound=False, nonecheck=False
# source: https://github.com/brainiak/rtAttenPenn/blob/9fc5bb8ae5485fef345736566f972ee538ef348c/highpass_gaussian_betweenruns.c

from __future__ import division
import numpy as np

# "cimport" is used to import special compile-time information about the numpy
# module (this is stored in a file numpy.pxd which is currently part of the
# Cython distribution).
cimport numpy as np
cimport cython

# Fix a datatype for our array
DTYPE = np.float64

# "ctypedef" assigns a corresponding compile-time type to DTYPE_t. For every
# type in the numpy module there's a corresponding compile-time type with a
# _t-suffix.
ctypedef np.float64_t DTYPE_t

# The builtin min and max functions works with Python objects, and are
# so very slow. So we create our own.
#  - "cdef" declares a function which has much less overhead than a normal
#    def function (but it is not Python-callable)
#  - "inline" is passed on to the C compiler which may inline the functions
#  - The C type "int" is chosen as return type and argument types
#  - Cython allows some newer Python constructs like "a if x else b", but
#    the resulting C file compiles with Python 2.3 through to Python 3.0 beta.
cdef inline int int_max(int a, int b): return a if a >= b else b
cdef inline int int_min(int a, int b): return a if a <= b else b

cdef inline np.ndarray[DTYPE_t, ndim=1] hp_convkernel(int hp_mask_size, int sigma):
    cdef np.ndarray[np.int_t, ndim=1] indices = np.arange(hp_mask_size * 2 + 1) - hp_mask_size
    cdef np.ndarray[DTYPE_t, ndim=1] result = np.exp(-0.5 * indices * indices / (sigma * sigma))
    return result

# Expect data in [voxel x time]
@cython.cdivision(True)
@cython.boundscheck(False)
@cython.wraparound(False)
def highpass(np.ndarray[DTYPE_t, ndim=2] data, int sigma):
    cdef int hp_mask_size = sigma * 3

    # Get number of voxels and time points
    cdef Py_ssize_t nrow = data.shape[0]
    cdef Py_ssize_t ncol = data.shape[1]
    cdef Py_ssize_t nv = nrow
    cdef Py_ssize_t nt = ncol

    cdef np.ndarray[DTYPE_t, ndim=1] hp_exp = hp_convkernel(hp_mask_size, sigma)

    # Declare indices
    cdef Py_ssize_t v, t, tt, tt_left, tt_right, dt

    # Declare inner variables
    cdef DTYPE_t c, c0, done_c0, w, A, B, C, D, N, tmpdenom

    # Initialize result
    cdef np.ndarray[DTYPE_t, ndim=2] result = np.empty_like(data)

    for v in range(nv):
        done_c0 = 0
        c0 = 0
        for t in range(nt):
            A = B = C = D = N = 0
            tt_left = int_max(t - hp_mask_size, 0)
            tt_right = int_min(t + hp_mask_size, nt - 1)

            for tt in range(tt_left, tt_right + 1):
                dt = tt - t
                w = hp_exp[dt + hp_mask_size]
                A += w * dt
                B += w * data[v, tt]
                C += w * dt * dt
                D += w * dt * data[v, tt]
                N += w

            tmpdenom = C * N - A * A

            if tmpdenom != 0:
                c = (B * C - A * D) / tmpdenom
                if done_c0 == 0:
                    c0 = c
                    done_c0 = 1

                result[v, t] = c0 + data[v, t] - c
            else:
                result[v, t] = data[v, t]

    return result
