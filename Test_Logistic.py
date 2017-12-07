import rtAttenPy
import contexttimer
import scipy.io

a = scipy.io.loadmat('logistic_in.mat')
b = scipy.io.loadmat('logistic_out.mat')

data = a['a']['data'][0][0]
labels = [x[0] if x[0] == 1 else -1 for x in a['a']['labels'][0][0]]
print(labels)

classifier = rtAttenPy.logistic(data, labels)

# TODO: Get testing data
#  classifier.predict(test)


