import rtAttenPy
import scipy.io
import numpy as np
from contexttimer import Timer

# Get highpass.tgz and tar zxvf
a = scipy.io.loadmat('highpass_in.mat')
b = scipy.io.loadmat('highpass_out.mat')

with Timer() as t:
    result = rtAttenPy.highpass_opt(a['a']['data'][0][0], 28)
print('New: %0.2fs' % t.elapsed)

np.testing.assert_array_almost_equal(result, expected)
