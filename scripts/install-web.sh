# Active python directory
source ~/.bashrc

# Install web interface tools
sudo yum -y install bzip2

# install node.js and npm
sudo yum -y install nodejs

# Install npm
pushd webInterface/rtAtten/web/
npm install
popd

# Install websockify environment
conda env create -f websockify.yml

sudo yum -y install epel-release
sudo yum -y install tigervnc-server
sudo yum -y install xclock
sudo yum -y install xdotool

cat <<EOT >> ~/.vnc/xstartup
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
#exec /etc/X11/xinit/xinitrc
xsetroot -solid grey -cursor_name left_ptr
xeyes
EOT

# get dcm2nii tool
pushd ~/Downloads
wget https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20180622/dcm2niix_27-Jun-2018_lnx.zip
unzip dcm2niix_27-Jun-2018_lnx.zip
popd
sudo mkdir -p /usr/local/bin
sudo cp ~/Downloads/dcm2niix /usr/local/bin

# In case the steps above don't work:
# Build dcm2niix didn't work, I get segmentation fault when running on images
#git clone https://github.com/rordenlab/dcm2niix.git
#sudo yum -y groupinstall 'Development Tools'
#sudo yum -y install libstdc++-static
#sudo yum -y install cmake
#mkdir dcm2niix/build
#cd dcm2niix/build
#cmake ..
#make
#sudo make install
## cp ../bin/dcm2niix /Tools

# create conda environment to run fsl instal
sudo yum -y install python2
# install FSL tools
# installation instructions https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation/Linux
pushd ~/Downloads
wget https://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py
sudo python2 fslinstaller.py -d /usr/local/fsl
popd

sudo yum -y install libpng12 libmng
sudo yum -y install xorg-x11-fonts-Type1 # to show fonts correctly
sudo yum -y install pigz
sudo yum -y install openblas.x86_64 openblas-devel.x86_64
sudo yum -y install freeglut-devel # might not be needed
sudo yum -y install glx-utils  # glxgears and glxinfo, maybe not needed
sudo yum -y install gtk2 # maybe not needed
sudo yum -y install libquadmath-devel # this allows you to access libraries
# Add fsl to path by editing ~/.bash_profile
cat <<EOT >> ~/.bash_profile
FSLDIR=/usr/local/fsl
. \$FSLDIR/etc/fslconf/fsl.sh
PATH=\$FSLDIR/bin:\$PATH
export FSLDIR PATH
EOT
source ~/.bash_profile

# To dispay on Mac with XQuartz must run this command in Mac shell or get X11 Gdk-ERROR
# UNCOMMENT IF YOU'RE RUNNING ON A MAC:
# defaults write org.macosforge.xquartz.X11 enable_iglx -bool true

# if you get a Gtk GModule warning like
# (fsleyes:15552): Gtk-WARNING **: GModule (/usr/lib64/gtk-2.0/2.10.0/immodules/im-ibus.so)
# Then you need to install the correct version of fsleyes, instructions here
# https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FSLeyes




