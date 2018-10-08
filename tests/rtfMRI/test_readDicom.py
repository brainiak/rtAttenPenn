import pytest
import os
import rtfMRI.ReadDicom as rd


def test_readDicom():
    dicomFile = os.path.join(os.path.dirname(__file__), 'test_input/001_000001_000001.dcm')
    vol1 = rd.readDicomFromFile(dicomFile, 64)
    assert vol1 is not None

    with open(dicomFile, 'rb') as fp:
        data = fp.read()
    vol2 = rd.readDicomFromBuffer(data, 64)
    assert vol2 is not None
    assert (vol1==vol2).all()
