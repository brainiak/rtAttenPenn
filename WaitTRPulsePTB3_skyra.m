function varargout = WaitTRPulsePTB3_skyra(numberPulses, varargin)% secs = WaitTRPulse(numberPulses)%% Waits to receive an integer number of TR pulses (numberPulses),% and returns GetSecs arrival time (secs) of last TR pulse.% (e.g., WaitTRPulseRowland(3); will wait for three TR pulses.)%% This function is a direct replacement for WaitScanner% when one wants to use the Rowland fMRI hand pucks instead% of the PST fMRI hand pucks.%% The function simply loops infinitely until the `~ key is pressed% a certain number of times or until the scanner sends a certain number% of TR pulses (which simulates the `~ key being pressed through the% Rowland% fMRI hand pucks) after which time the calling program will continue.%% Note: For the very first iteration of the WHILE-loop to be% as fast as possible, have the main program call KbCheck(-1) at least% once before calling WaitTRPulseRowland so that the KbCheck(-1) MEX-file% is already loaded into memory.%% 12 Sep 2002  dws  Created by Daniel Shima, Vanderbilt Vision Research Center.% 26 Sep 2002  dws  Added optional argument to make it wait for next TR pulse.%  2 Oct 2002  dws  Added secs return value.% 13 Nov 2002  dws  Revised to wait for multiple pulses.%  1 Sep 2003  djy  Revised to wait '%5 (24)' and renamed from WaitTRRowland.%  9 Jun 2008  abl  Revised for different keycode for OSX Psychtoolbox (34, not 24)recorded = false;secs = -1;loop_delay = .0005;DEVICENAME = 'Current Designs, Inc. 932';%DEVICENAME = '932'; %name of device you want to poll%DEVICENAME = 'Apple Internal Keyboard / Trackpad';%use this line if you want to mimic the trigger pulse (on a Mac) for debugging purposes[index devName] = GetKeyboardIndices;for device = 1:length(index) if strcmp(devName(device),DEVICENAME)   DEVICE = index(device); endendDEVICE = -1if nargin > 1 && strcmp(varargin{nargin-1}, 'debug')    n_dsecs = 2000;    dsecs = zeros(n_dsecs,1);    if nargin < 2 || nargin > 3        error('Wrong Number of Arguments')    elseif nargin == 3        for i = 1:numberPulses            index = 0;            while (GetSecs<varargin{1})                WaitSecs(loop_delay);                index = index + 1;                [keyIsDown,secs,keyCode, delsecs] = KbCheck(DEVICE);                dsecs(index) = delsecs*1000;                if (~keyCode(34))                    break;                end            end            while (GetSecs<varargin{1})                WaitSecs(loop_delay);                index = index + 1;                [keyIsDown,secs,keyCode, delsecs] = KbCheck(DEVICE);                dsecs(index) = delsecs*1000;                if (keyIsDown)                    if (keyCode(34))                        recorded = true;                        break;                    end                end            end        end    else        for i = 1:numberPulses            index = 0;            while (1)                WaitSecs(loop_delay);                index = index + 1;                [keyIsDown,secs,keyCode, delsecs] = KbCheck(DEVICE);                dsecs(index) = delsecs*1000;                if (~keyCode(34))                    break;                end            end            while (1)                WaitSecs(loop_delay);                index = index + 1;                [keyIsDown,secs,keyCode, delsecs] = KbCheck(DEVICE);                dsecs(index) = delsecs*1000;                if (keyIsDown)                    if (keyCode(34))                        recorded = true;                        break;                    end                end            end        end    end    varargout{1} = secs;    varargout{2} = recorded;    varargout{3} = dsecs;else    if nargin < 1 || nargin > 2        error('Wrong Number of Arguments')    elseif nargin == 2        for i = 1:numberPulses            while (GetSecs<varargin{1})                WaitSecs(loop_delay);                [keyIsDown,secs,keyCode] = KbCheck(DEVICE);                if (~keyCode(34))                    break;                end            end            while (GetSecs<varargin{1})                WaitSecs(loop_delay);                [keyIsDown,secs,keyCode] = KbCheck(DEVICE);                if (keyIsDown)                    if (keyCode(34))                        recorded = true;                        break;                    end                end            end        end    else        for i = 1:numberPulses            while (1)                WaitSecs(loop_delay);                [keyIsDown,secs,keyCode] = KbCheck(DEVICE);                if (~keyCode(34))                    break;                end            end            while (1)                WaitSecs(loop_delay);                [keyIsDown,secs,keyCode] = KbCheck(DEVICE);                if (keyIsDown)                    if (keyCode(34))                        recorded = true;                        break;                    end                end            end        end    end    varargout{1} = secs;    varargout{2} = recorded;end% if(~recorded)%     secs = GetSecs;% end