"""
The code and logic for the real-time attention fMRI experiment
"""
from enum import Enum, unique
from ..MsgTypes import MsgEvent
from ..BaseModel import BaseModel

class RtAttenModel(BaseModel):
    def __init__(self):
        super().__init__(self)
        self.cache = {}

    def TrainingData(self, msg):
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def Predict(self, msg):
        return self.createReplyMessage(msg.id, MsgEvent.Success)

    def TrainModel(self, msg):
        return self.createReplyMessage(msg.id, MsgEvent.Success)


"""
TrainingDataClass - Module for accumulating and pre-processing training data
"""
class TrainingData:
    """Collect and pre-process data that will be used to train a ML model"""
    def __init__(self):
        pass

    def initialize(self):
        pass

    def addData(self, dataId, data):
        pass

    def finalize(self):
        # write out to file
        pass


"""
TrainModelClass - Module for training the pre-collected and processed data
"""
class TrainModel:
    """Using data in a TrainDataClass, train the data to create a ML predictive model"""
    def __init__(self):
        pass

    def trainModel(self):
        pass

    def finalize(self):
        # write model out to a file
        pass


"""
PredictionDataClass - Module to accumulate input data for predictions and to make predictions
"""
class PredictionData:
    """Collect, pre-process and do prediction of a data element"""
    def __init__(self):
        pass

    def initialize(self):
        pass

    def predict(self, dataId, data):
        pass

    def finialize(self):
        # write out data to file
        pass


@unique
class BlockType(Enum):
    Train   = 1
    Predict = 2
