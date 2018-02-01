#!/usr/bin/env python3
import numpy as np  # type: ignore
import scipy.special as scisp  # type: ignore


def Test_L2_RLR_realtime(trainedModel, examplesTest, labelsTest):
    assert examplesTest.shape[0] != 1
    assert len(examplesTest.shape) == 1, "Assertion: expecting 1D array"

    x = np.dot(examplesTest, trainedModel.weights) + trainedModel.biases
    activations = np.transpose(scisp.expit(x))
    # reduce dimensions with only 1 entry, i.e. go from array(2,1) to array(2)
    activations = np.squeeze(activations)

    labelsPredicted = np.argmax(activations, axis=0)

    if np.any(labelsTest):
        if labelsPredicted == np.flatnonzero(labelsTest):
            testAccuracy = 1
        else:
            testAccuracy = 0
    else:
        testAccuracy = np.nan

    return (labelsPredicted, labelsTest, testAccuracy, activations)
