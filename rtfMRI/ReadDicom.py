import numpy as np  # type: ignore
try:
    import pydicom as dicom  # type: ignore
except ModuleNotFoundError:
    import dicom  # type: ignore


def readDicom(filename, sliceDim):
    '''The raw dicom file will be a 2D picture with multiple slices tiled together.
       We need to separate the slices and form a volume from them.
    '''
    sliceWidth = sliceDim
    sliceHeight = sliceDim

    dicomImg = dicom.read_file(filename)
    image = dicomImg.pixel_array

    dicomHeight, dicomWidth = image.shape
    numSlicesPerRow = dicomWidth // sliceWidth
    numSlicesPerCol = dicomHeight // sliceHeight

    max_slices = numSlicesPerRow * numSlicesPerCol
    volume = np.full((sliceWidth, sliceHeight, max_slices), np.nan)

    sliceNum = 0
    for row in range(numSlicesPerCol):
        for col in range(numSlicesPerRow):
            assert sliceNum < max_slices
            rpos = row * sliceHeight
            cpos = col * sliceWidth
            slice = image[rpos: rpos+sliceHeight, cpos: cpos+sliceWidth]
            volume[:, :, sliceNum] = slice
            sliceNum += 1
    return volume, dicomImg


def applyMask(volume, roiInds):
    # maskedVolume = np.zeros(volume.shape, dtype=float)
    # maskedVolume.flat[roiInds] = volume.flat[roiInds]
    maskedVolume = volume.flat[roiInds]
    return maskedVolume
