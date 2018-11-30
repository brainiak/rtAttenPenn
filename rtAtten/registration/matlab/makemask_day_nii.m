function makemask_day1(subjectNum,dayNum, project_dir)
%%
projectName = 'rtAttenPenn';

if strcmp(class(subjectNum), 'char')
    subjectNum = str2num(subjectNum)
end

if strcmp(class(dayNum), 'char')
    dayNum = str2num(dayNum)
end

current_dir = pwd
save_dir = fullfile(project_dir, ['/data/subject' num2str(subjectNum), '/day' num2str(dayNum)]);
process_dir = [save_dir '/' 'reg' '/'];
roi_name = 'wholebrain_mask';
addpath(genpath(project_dir));

cd(process_dir);
%% create mask file for real-time dicom files

%load registered anatomical ROI
if dayNum==1
        hdr = nii_read_header([roi_name '_exfunc.nii']);
        volData = nii_read_volume(hdr);
	functionalFN = 'exfunc';
else
        hdr = nii_read_header(['mask12func2' '.nii']);
        volData = nii_read_volume(hdr);
	functionalFN = 'exfunc2';
end
hdr = nii_read_header([functionalFN '_brain.nii']);
volExtFunc = nii_read_volume(hdr);

%rotate anatomical ROI to be in the same space as the mask - check that this works for different scans/ROIs
anatMaskRot = zeros(size(volExtFunc));
brainExtRot = zeros(size(volExtFunc));
for i = 1:size(volData,3)
    anatMaskRot(:,:,i) = rot90(volData(:,:,i)); %rotates entire slice by 90 degrees
    brainExtRot(:,:,i) = rot90(volExtFunc(:,:,i));
end

%overwrite whole-brain mask
mask = logical(anatMaskRot); %make it so it's just 1's and 0's
brainExt = logical(brainExtRot);
allinMask = find(anatMaskRot);
allinBrainExt = find(brainExt);
mask_indices = allinMask(find(ismember(allinMask,allinBrainExt))); %these are the good mask indices that are only brain
%mask_indices = allinMask(find(allinMask)); % just use all the ones from the registration
[gX gY gZ] = ind2sub(size(mask),mask_indices);
mask_brain = zeros(size(mask,1),size(mask,2),size(mask,3));
for j=1:length(mask_indices)
    mask_brain(gX(j),gY(j),gZ(j)) = 1;
end

checkMask = 0;
if checkMask
    plot3Dbrain(mask,[], 'mask')    
    plot3Dbrain(mask_brain, [], 'mask_brain')
end
% use the mask that has been checked there's nothing outside the functional
% brain
mask=mask_brain;
%save anatomical mask
save([project_dir '/data/subject' num2str(subjectNum) '/day' num2str(dayNum) '/mask_' num2str(subjectNum) '_' num2str(dayNum) '_nii'],'mask');
fprintf('Done with mask creation\n');
% if cd into the directory, cd out of it back to the general exp folder
cd(current_dir);

end
