#!/bin/bash
#Author: Anne
#Purpose: register t1 to standard space
# Things it does

export LD_LIBRARY_PATH=.:/usr/local/MATLAB/MATLAB_Compiler_Runtime/v83/runtime/glnxa64:/usr/local/MATLAB/MATLAB_Compiler_Runtime/v83/bin/glnxa64:/usr/local/MATLAB/MATLAB_Compiler_Runtime/v83/sys/os/glnxa64:$LD_LIBRARY_PATH

export XAPPLRESDIR=/usr/local/MATLAB/MATLAB_Compiler_Runtime/v83/X11/app-defaults

source globals.sh   
if [ $dryrun = true ]; then
  echo "DRY RUN..."
fi
echo "subject number is $subjectNum, day $dayNum, run $runNum"
subject_save_path=$data_path/subject$subjectNum/day$dayNum/reg
# move into subjects directory
cd $subject_save_path
echo "moving into folder: $subject_save_path"
if [ $dayNum -gt 1 ]
then
  if [ -z $dryrun ] || [ $dryrun != true ]; then
    functional2FN=exfunc2
    if [ -f $functional2FN'_'brain.nii.gz ]; then echo "ungzipping epi"; gunzip -f $functional2FN'_'brain.nii.gz ; fi

    if [ -f mask12func2.nii.gz ]; then echo "ungzipping mask"; gunzip -f mask12func2.nii.gz ; fi
  fi
fi
if [ $dayNum -eq 1 ]
then
  if [ -z $dryrun ] || [ $dryrun != true ]; then
    functionalFN=exfunc
    if [ -f $functionalFN'_'brain.nii.gz ]; then echo "ungzipping epi"; gunzip -f $functionalFN'_'brain.nii.gz ; fi

    if [ -f $roi_name'_'exfunc.nii.gz ]; then echo "ungzipping mask"; gunzip -f $roi_name'_'exfunc.nii.gz ; fi
  fi
fi
echo "running matlab script to make mask"
cd $code_path
if [ -z $dryrun ] || [ $dryrun != true ]; then
  ./makemask_nii $subjectNum $dayNum $data_path
  #matlab -nodesktop -nodisplay -r "try; makemask_day_nii($subjectNum,$dayNum); catch me; fprintf('%s / %s\n', me.identifier, me.message); end;exit"
fi
echo "done!"