import rtAttenPy
import contexttimer
import scipy.io

a = scipy.io.loadmat('logistic_in.mat')
b = scipy.io.loadmat('logistic_out.mat')

data = a['a']['data'][0][0]
labels = [x[0] fpr x in a['a']['labels'][0][0]]

classifier = rtAttenPy.logistic(data, labels)

# TODO: Get testing data
#  classifier.predict(test)


