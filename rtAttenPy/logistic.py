import numpy as np
import sklearn.linear_model

# TODO: This is not the API we want for sklearn classifier


def logistic(data, labels):
    classifier = sklearn.linear_model.LogisticRegression()
    classifier.fit(data, labels)
    return classifier
