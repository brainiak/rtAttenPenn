import rtAttenPy
import scipy.io
import numpy as np

# Get highpass.tgz and tar zxvf
a = scipy.io.loadmat('highpass_in.mat')
b = scipy.io.loadmat('highpass_out.mat')

result = rtAttenPy.highpass(a['a']['data'][0][0], 28)
expected = np.transpose(b['b'])

np.testing.assert_array_almost_equal(result, expected)
