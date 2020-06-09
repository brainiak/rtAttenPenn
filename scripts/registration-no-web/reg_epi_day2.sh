#!/bin/bash
#Author: Anne
#Purpose: register t1 to standard space
# Things it does
# 1. skull strip data
# 2. register to standard space
# 3. invert transformation

source globals.sh

if [ $dryrun = true ]; then
  echo "DRY RUN..."
fi
echo "subject number is $subjectNum, day $dayNum, run $runNum"
subject_save_path=$data_path/subject$subjectNum/day$dayNum/reg
subject_day1_path=$data_path/subject$subjectNum/day1/reg
# move into subjects directory
mkdir -pv $subject_save_path
cd $subject_save_path
echo "moving into folder: $subject_save_path"

echo "subject name is $subjName"
echo "looking for dicoms in $scanFolder"

# Process t1-weighted MPRAGE and check brain extraction!
functionalFN=exfunc
functional2FN=exfunc2
fileN=6
exfunc_str=$(printf "%s/001_0000%02d_0000%02d.dcm" "$scanFolder" "$functionalScan" "$fileN")
if [ $1 -eq 1 ]
then
  if [ -z $dryrun ] || [ $dryrun != true ]; then
    dcm2niix -f $functional2FN -z y -o $subject_save_path -s y $exfunc_str
  fi
fi
if [ $2 -eq 1 ]
then
  if [ -z $dryrun ] || [ $dryrun != true ]; then
    flirt -v -dof 6 -in $subject_day1_path/$functionalFN'.'nii.gz -ref $functional2FN'.'nii.gz -out func12func2 -omat func12func2.mat
    flirt -v -in $subject_day1_path/wholebrain_mask_exfunc -ref $functional2FN'.'nii.gz -applyxfm -init func12func2.mat -interp nearestneighbour -out mask12func2
  fi
fi

if [ -z $dryrun ] || [ $dryrun != true ]; then
  bet $functional2FN'.'nii.gz $functional2FN'_'brain -R -m -v
  $VIEWCMD $functional2FN'.'nii.gz $functional2FN'_'brain.nii.gz &

  # now check on past mask again
  $VIEWCMD $functional2FN'.'nii.gz $functional2FN'_'brain_mask.nii.gz mask12func2.nii.gz & 
fi

echo="copying this version for safe keeping!"
cp $code_path/reg_epi_day2.sh $data_path/subject$subjectNum/usedscripts/reg_epi_day2_$dayNum'.'sh
cp $code_path/globals.sh $data_path/subject$subjectNum/usedscripts/globals_day$dayNum.sh

cd $data_path
