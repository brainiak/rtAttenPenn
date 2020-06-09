#!/bin/bash
#Author: Anne
#Purpose: register t1 to standard space
# Things it does

source globals.sh   
if [ $dryrun = true ]; then
  echo "DRY RUN..."
fi
echo "subject number is $subjectNum, day $dayNum, run $runNum"
subject_save_path=$data_path/subject$subjectNum/day$dayNum/reg
subject_day_path=$data_path/subject$subjectNum/day$dayNum
# move into subjects directory
cd $subject_save_path
echo "moving into folder: $subject_save_path"
echo "running python script to make mask"
cd $code_path
if [ -z $dryrun ] || [ $dryrun != true ]; then
 python makemask_day.py $subjectNum $dayNum $data_path
fi
echo "done!"
