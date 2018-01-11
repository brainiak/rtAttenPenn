import rtAttenPy_v0
import scipy.io
import numpy as np
from contexttimer import Timer

# Get highpass.tgz and tar zxvf
a = scipy.io.loadmat('test_input/highpass_in.mat')
b = scipy.io.loadmat('test_input/highpass_out.mat')

data = a['a']['data'][0][0]

with Timer() as t:
    #  result = rtAttenPy_v0.highpass.highpass(np.transpose(data), 28)
    result = rtAttenPy_v0.highpass(np.transpose(data), 28, False)
print('New: %0.2fs' % t.elapsed)
np.testing.assert_array_almost_equal(np.transpose(result), b['b'])
