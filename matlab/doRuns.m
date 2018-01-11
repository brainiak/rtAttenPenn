
subjectNum = 3;
date_pattern = '20180105T';

for runNum = 1:3
    fprintf("run %d\n", runNum)
    pats = RealTimePunisherFileProcess(subjectNum, runNum, date_pattern);
end