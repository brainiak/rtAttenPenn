import pytest
import os
import rtfMRI.ReadDicom as rd


def test_readDicom():
    dicomFile = os.path.join(os.path.dirname(__file__), 'test_input/001_000001_000001.dcm')
    vol, dicom = rd.readDicom(dicomFile, 64)
    assert vol is not None
    assert dicom is not None
