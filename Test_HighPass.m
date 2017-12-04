load highpass_in.mat
load highpass_out.mat

tic
result = HighPassBetweenRuns(a.data, a.TR, a.cutoff);
toc

all(all(result == b))

result = HighPassRealTime(a.data, a.TR, a.cutoff);