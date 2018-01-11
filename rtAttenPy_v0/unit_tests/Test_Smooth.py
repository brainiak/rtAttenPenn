import math
import scipy.io
import rtAttenPy_v0
import numpy as np
from contexttimer import Timer


print('Loading data')
# Get smooth.tgz and tar zxvf
a = scipy.io.loadmat('test_input/smooth_in.mat')
b = scipy.io.loadmat('test_input/smooth_out.mat')

# Full-width half-max of gaussian
FWHM = a['a']['FWHM'][0][0][0][0]

# Dimension of pattern
dims = a['a']['roiDims'][0][0][0]

# Indices
inds = a['a']['roiInds'][0][0] - 1
unraveled_inds = np.unravel_index(inds, dims, order='F')
inds = np.ravel_multi_index(unraveled_inds, dims, order='C')

data = a['a']['raw'][0][0][0]

# Voxel size in mm
voxel_size = 3

# Sigma
sigma = (FWHM / voxel_size) / (2 * math.sqrt(2 * math.log(2)))

print('Computing smooth')
with Timer() as t:
    result = rtAttenPy_v0.smooth(a['a']['raw'][0][0].astype(float), dims,
                              inds, FWHM)

print(t.elapsed)

#print(max(abs((result - b['b']) / b['b'])))
