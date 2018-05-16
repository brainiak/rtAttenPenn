import numpy as np  # type: ignore
from . import highpass

def highPassBetweenRuns(A_matrix, TR, cutoff):
    return np.transpose(highpass(np.transpose(A_matrix), cutoff/(2*TR), False))


def highPassRealTime(A_matrix, TR, cutoff):
    full_matrix = np.transpose(highpass(np.transpose(A_matrix), cutoff/(2*TR), True))
    return full_matrix[-1, :]
