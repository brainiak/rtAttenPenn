import sklearn.linear_model

# TODO: This is not the API we want for sklearn classifier


def logistic(data, labels):
    classifier = sklearn.linear_model.LogisticRegression(solver='sag')
    classifier.fit(data, labels)
    return classifier
