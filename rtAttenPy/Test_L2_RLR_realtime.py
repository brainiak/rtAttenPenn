#!/usr/bin/env python3
import numpy as np
import scipy.special as scisp

def Test_L2_RLR_realtime(trainedModel, examplesTest, labelsTest):
    if examplesTest.shape[1] == 1:
        examplesTest = np.transpose(examplesTest)

    nExamples = examplesTest.shape[0]

    # activations = exp( examplesTest * trainedModel.weights + repmat(trainedModel.biases,nExamples,1) )' ./ (1+exp( examplesTest * trainedModel.weights + repmat(trainedModel.biases,nExamples,1) )');

    x = np.dot(examplesTest, trainedModel.weights) + np.tile(trainedModel.biases, [nExamples, 1])
    activations = np.transpose(scisp.expit(x))

    labelsPredicted = np.argmax(activations, axis=0)

    if np.any(labelsTest):
        if labelsPredicted == np.nonzero(labelsTest): # TODO test this direction
            testAccuracy = 1
        else:
            testAccuracy = 0
    else:
        testAccuracy = np.nan

    return (labelsPredicted,labelsTest,testAccuracy,activations)
