#!/usr/bin/env python3
import numpy as np
import scipy.special as scisp

def Test_L2_RLR_realtime(trainedModel, examplesTest, labelsTest):
    assert examplesTest.shape[0] != 1
    assert len(examplesTest.shape) == 1, "Assertion: expecting 1D array"

    x = np.dot(examplesTest, trainedModel.weights) + trainedModel.biases
    activations = np.transpose(scisp.expit(x))

    labelsPredicted = np.argmax(activations, axis=0)

    if np.any(labelsTest):
        if labelsPredicted == np.nonzero(labelsTest)[0]:
            testAccuracy = 1
        else:
            testAccuracy = 0
    else:
        testAccuracy = np.nan

    return (labelsPredicted,labelsTest,testAccuracy,activations)
