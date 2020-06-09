#!/bin/bash
#Author: Anne
#Purpose: register t1 to standard space
# Things it does
# 1. skull strip data
# 2. register to standard space
# 3. invert transformation
# input is if you're running it the first time and have to convert from dicoms

source globals.sh

if [ ! -z $dryrun ] && [ $dryrun = true ]; then
  echo "DRY RUN..."
fi

echo "subject number is $subjectNum, day $dayNum, run $runNum"
subject_save_path=$data_path/subject$subjectNum/day$dayNum/reg
# move into subjects directory
mkdir -pv $subject_save_path
cd $subject_save_path
echo "moving into folder: $subject_save_path"
echo "looking for dicoms in $scanFolder"

# Process t1-weighted MPRAGE and check brain extraction!
highresFN=highres
highresfiles_genstr=$(printf "%s/001_0000%02d_0*" "$scanFolder" "$highresScan")
if [ $1 -eq 1 ]
then
  mkdir -pv $subject_save_path/tempdcm
  cp $highresfiles_genstr $subject_save_path/tempdcm/
        if [ -z $dryrun ] || [ $dryrun != true ]; then
          dcm2niix -f highres -o $subject_save_path/ -z y $subject_save_path/tempdcm/
        fi

  rm -r $subject_save_path/tempdcm
fi

if [ -z $dryrun ] || [ $dryrun != true ]; then
  bet $highresFN.nii.gz $highresFN'_'brain.nii.gz -R -m -f $fParam -v
  $VIEWCMD $highresFN.nii.gz $highresFN'_'brain.nii.gz $highresFN'_'brain_mask.nii.gz & 
fi

echo "copying this version of file into subject folder for safe keeping!"
mkdir -pv $data_path/subject$subjectNum/usedscripts/
cp $code_path/skullstrip_t1.sh $data_path/subject$subjectNum/usedscripts/skullstrip_T1.sh
cp $code_path/globals.sh $data_path/subject$subjectNum/usedscripts/globals_day$dayNum.sh
echo "done!"
