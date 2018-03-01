import scipy
import numpy as np

mask = np.full((9,9), np.nan)
mask[2:7, 2:7] = 1
mask[4, 4] = np.nan

A = mask * 10
A[np.isnan(mask)] = 0  # A[mask!=mask] = 0

norm = mask.copy()
norm[np.isnan(mask)] = 0  # norm[mask!=mask] = 0

Asmooth = scipy.ndimage.filters.gaussian_filter(A, 1)
Nsmooth = scipy.ndimage.filters.gaussian_filter(norm, 1)

result = Asmooth / Nsmooth
result[mask!=mask] = 0
