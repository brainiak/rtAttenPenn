load 'smooth_in.mat'
load 'smooth_out.mat'

tic
result = SmoothRealTime(a.raw, a.roiDims, a.roiInds, a.FWHM);
toc

all(transpose(result) == b)