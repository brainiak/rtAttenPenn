load(highpass_in.mat);
load(highpass_out.mat);

result = HighPassBetweenRuns(a.data, a.TR, a.cutoff);

all(all(result == b))