#!/usr/bin/bash

clientAddr="128.112.0.0"
serverAddr="128.112.102.11"
servicePort="5200"

# Install git
if [[ `command -v git` == "" ]]; then
  if [[ "$OSTYPE" == "linux-gnu" ]]; then
    os=`cat /etc/*release | grep ^NAME`
    if echo $os | grep Ubuntu; then
      sudo apt install -y git
    elif echo $os | grep CentOS; then
      sudo yum install -y git
    elif echo $os | grep "Red Hat"; then
        sudo yum install -y git
    fi
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    # Assumes user has brew
    brew install git
  fi
else
  echo "Git already installed"
fi

if [[ `command -v conda` == "" ]]; then
    echo "INSTALL MINICONDA"
    if [ ! -e  ~/Downloads ]; then
        echo "Make direcorty ~/Downloads"
        mkdir ~/Downloads
    fi
    pushd ~/Downloads
    if [[ $OSTYPE == linux* ]]; then
        echo "Install Miniconda on Linux"
        wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
        bash Miniconda3-latest-Linux-x86_64.sh -b
        echo export PATH="$HOME/miniconda3/bin:\$PATH" >> ~/.bashrc
        echo ". $HOME/miniconda3/etc/profile.d/conda.sh" >> ~/.bashrc
        source ~/.bashrc
    elif [[ $OSTYPE == darwin* ]]; then
        echo "Install Miniconda on MacOSX"
        brew install wget
        wget https://repo.continuum.io/miniconda/Miniconda3-latest-MacOSX-x86_64.sh
        bash Miniconda3-latest-MacOSX-x86_64.sh -b
        echo export PATH="$HOME/miniconda3/bin:\$PATH" >> ~/.bash_profile
        echo ". $HOME/miniconda3/etc/profile.d/conda.sh" >> ~/.bash_profile
        source ~/.bash_profile
    else
        echo "Unrecognized OS Type $OSTYPE"
        exit -1
    fi
    popd
else
    echo "Miniconda already installed"
fi
conda update -y conda

echo "INSTALL RTATTEN_PENN SOFTWARE"
if [[ $PWD =~ rtAttenPenn$ ]]; then
    echo "Pull latest updates for rtAttenPenn"
    git pull
elif [ -e ./rtAttenPenn ]; then
    echo "Pull latest updates for rtAttenPenn"
    cd rtAttenPenn/
    git pull
else
    echo "Git clone rtAttenPenn"
    git clone https://github.com/brainiak/rtAttenPenn.git
    cd rtAttenPenn/
fi

if [ ! -e "environment.yml" ]; then
    echo "Missing environment.yml file"
    exit -1;
fi

# Install rtfMRI and rtAtten
conda env create -f environment.yml
source activate rtAtten
python setup.py install

# Install certificates
pushd certs
rm rtfMRI*
randNum=$RANDOM
openssl req -newkey rsa:2048 -nodes -keyout rtfMRI_rsa-$randNum.private -x509 -days 365 -out rtfMRI-$randNum.crt \
  -subj "/C=US/ST=New Jersey/L=Princeton/O=Princeton University/CN=rtAtten"; \
ln -s rtfMRI_rsa-$randNum.private rtfMRI_rsa.private; \
ln -s rtfMRI-$randNum.crt rtfMRI.crt
popd # certs

# Install conda autoenv
# TODO: Assign this path to variable; we use it a lot
$HOME/miniconda3/bin/python -m pip install conda-autoenv
echo "source \$HOME/miniconda3/bin/conda_autoenv.sh" >> ~/.bashrc
source ~/.bashrc

# For Server Only
if [[ "$OSTYPE" == "linux-gnu" ]]; then
  # Install service
  sudo cp scripts/rtatten-server.service /usr/lib/systemd/system
  sudo systemctl enable rtatten-server

  # Set iptables
  # sudo iptables -I INPUT 6 -p tcp -s $clientAddr/16 --dport $servicePort -j ACCEPT
  sudo iptables -I INPUT 6 -p tcp --dport 5200 -j ACCEPT
fi

# echo "START SERVER"
#
# python ServerMain.py -p $servicePort

# For Client Only
# echo "START CLIENT"
# scp $serverAddr:~/rtAttenPenn/certs/rtfMRI.crt ./certs/rtfMRI.crt
# python ClientMain.py -e rtAttenPennCfg.toml -a $serverAddr -p $servicePort
