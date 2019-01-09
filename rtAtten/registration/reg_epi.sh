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
# move into subjects directory
mkdir -pv $subject_save_path
cd $subject_save_path
echo "moving into folder: $subject_save_path"

echo "subject name is $subjName"
echo "looking for dicoms in $scanFolder"

# Process t1-weighted MPRAGE and check brain extraction!
functionalFN=exfunc
highresFN=highres
fileN=6
exfunc_str=$(printf "%s/001_0000%02d_0000%02d.dcm" "$scanFolder" "$functionalScan" "$fileN")
exfunc2highres_mat=example_func2highres
highres2exfunc_mat=highres2example_func

# remove previous functionalFN files if they exist
find . -name "$functionalFN*.nii.gz" -delete

if [ $1 -eq 1 ]
then
  if [ -z $dryrun ] || [ $dryrun != true ]; then
    dcm2niix -f $functionalFN -z y -o $subject_save_path -s y $exfunc_str
  fi
fi
if [ $2 -eq 1 ]
then
  if [ -z $dryrun ] || [ $dryrun != true ]; then
    # now register to highres!
    exfunc2highres_mat=example_func2highres
    highres2exfunc_mat=highres2example_func
    epi_reg -v --epi=$functionalFN --t1=$highresFN --t1brain=$highresFN'_'brain --out=$exfunc2highres_mat
    convert_xfm -inverse -omat $highres2exfunc_mat'.'mat $exfunc2highres_mat'.'mat
    # now register mask to all data
    applywarp -v -i $code_path/$roi_name'.'nii.gz -r $functionalFN'.'nii.gz -o $roi_name'_'exfunc.nii.gz -w standard2highres_warp.nii.gz --postmat=$highres2exfunc_mat'.'mat
    # check after here that the applied warp is binary and in the right
    # orientation so we could just apply to nifti files afterwards
  fi
fi
if [ -z $dryrun ] || [ $dryrun != true ]; then
  bet $functionalFN'.'nii.gz $functionalFN'_'brain.nii.gz -R -m -v
  export DISPLAY=localhost:1; fsleyes $functionalFN'.'nii.gz $functionalFN'_'brain.nii.gz $functionalFN'_'brain_mask.nii.gz &
fi

echo "copying this version of file into subject folder for safe keeping!"
mkdir -pv $data_path/subject$subjectNum/usedscripts/
cp $code_path/reg_epi.sh $data_path/subject$subjectNum/usedscripts/reg_epi.sh
cd $code_path
echo "done!, moving into project path"
