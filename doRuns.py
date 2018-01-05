#!/usr/bin/env python3
import rtAttenPy

trace_file_date_pattern = '20180105T145'
subjectNum = 3

for runNum in (1, 2):
    trace_file_pattern = 'trace_params_run' + str(runNum) + '_' + trace_file_date_pattern + '*.mat'
    trace_file = rtAttenPy.findNewestFile('data/output', trace_file_pattern)
    print("Start run {}: {}".format(runNum, trace_file))
    rtAttenPy.realTimePunisherProcess(subjectNum, runNum, ValidationFile=trace_file)
    print("End run {}".format(runNum))
