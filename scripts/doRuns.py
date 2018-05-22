#!/usr/bin/env
import os
import sys
# fix up the module search path to be the rtAtten project path
scriptPath = os.path.dirname(os.path.realpath(__file__))
rootPath = os.path.join(scriptPath, "../")
sys.path.append(rootPath)

import rtAttenPy_v0

trace_file_date_pattern = '20180208T'
subjectNum = 3

# for runNum in (1,):
for runNum in (1, 2, 3):
    trace_file_pattern = 'trace_params_run' + str(runNum) + '_' + trace_file_date_pattern + '*.mat'
    trace_file = rtAttenPy_v0.findNewestFile('data/output', trace_file_pattern)
    print("Start run {}: {}".format(runNum, trace_file))
    rtAttenPy_v0.realTimePunisherProcess(subjectNum, runNum, ValidationFile=trace_file)
    print("End run {}".format(runNum))
