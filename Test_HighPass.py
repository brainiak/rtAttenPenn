import rtAttenPy
import rtAttenPy.highpass
import scipy.io
import numpy as np
from contexttimer import Timer

# Get highpass.tgz and tar zxvf
a = scipy.io.loadmat('highpass_in.mat')
b = scipy.io.loadmat('highpass_out.mat')

data = a['a']['data'][0][0]

with Timer() as t:
    result = rtAttenPy.highpass.highpass(np.transpose(data), 28)
print('New: %0.2fs' % t.elapsed)
np.testing.assert_array_almost_equal(np.transpose(result), b['b'])

