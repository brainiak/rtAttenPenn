import math
import numpy as np
import scipy.ndimage


def smooth(data, dims, inds, fwhm, voxel_size=3):
    """smooth

    Convert a 1-dimensional array into 3D for gaussian smoothing

    :param data: 1D np.array of last pattern acquired [1 x voxels]
    :param dims: roi dimensions [mask width x mask height x slices]
    :param inds: roi indices [= np.flatnonzero(mask)]
    :param fwhm: full-width half-max of gaussian
    :param voxel_size: voxel size in mm
    """
    # The smooth result can be distorted by zeros in the masked ares.
    # Normalize this out by dividing by a similarly smoothed array with 1s in then
    # non-masked area.
    mask = np.full(dims, np.nan)
    mask.flat[inds] = 1
    norm = mask.copy()
    norm[np.isnan(mask)] = 0

    vol = np.zeros(dims, dtype=float)
    vol.flat[inds] = data

    # TODO: We let SciPy determine window size
    # https://stackoverflow.com/questions/25216382/gaussian-filter-in-scipy
    #  t = int((((3 - 1) / 2) - 0.5) / sigma)
    sigma = (fwhm / voxel_size) / (2 * math.sqrt(2 * math.log(2)))

    # TODO - in test_mode put a comparison here to the base matlab volume
    # Validated by hand on select instances that vol is identical to the vol used in matlab run

    volSmooth = scipy.ndimage.filters.gaussian_filter(vol, sigma)
    normSmooth = scipy.ndimage.filters.gaussian_filter(norm, sigma)
    normSmooth[np.where(normSmooth == 0)] = 1

    resultVol = volSmooth / normSmooth
    resultVol[np.isnan(mask)] = np.nan

    result = resultVol.flat[inds]

    return result
