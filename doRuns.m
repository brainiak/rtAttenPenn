
subjectNum = 3;
date_pattern = '20171122T';

for runNum = 1:2
    fprintf("run %d\n", runNum)
    pats = RealTimePunisherFileProcess(subjectNum, runNum, date_pattern);
end