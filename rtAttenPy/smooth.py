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
    vol = np.zeros(dims, dtype=float)
    vol.flat[inds] = data

    # TODO: We let SciPy determine window size
    # https://stackoverflow.com/questions/25216382/gaussian-filter-in-scipy
    #  t = int((((3 - 1) / 2) - 0.5) / sigma)
    sigma = (fwhm / voxel_size) / (2 * math.sqrt(2 * math.log(2)))

    return scipy.ndimage.filters.gaussian_filter(vol, sigma).flat[inds]
