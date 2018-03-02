#!/usr/bin/bash
clientAddr="128.112.0.0"
serverAddr="128.112.102.11"
servicePort="5200"

echo "INSTALL MINICONDA"
if [ ! -e  ~/Downloads ]; then
    echo "Make direcorty ~/Downloads"
    mkdir ~/Downloads
fi
pushd ~/Downloads
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b
popd
echo export PATH="$HOME/miniconda3/bin:\$PATH" >> ~/.bashrc
echo ". $HOME/miniconda3/etc/profile.d/conda.sh" >> ~/.bashrc
source ~/.bashrc
conda update -y conda

echo "INSTALL RTATTEN_PENN SOFTWARE"
if [ ! -e  ./rtAttenPenn ]; then
    echo "Git clone rtAttenPenn"
    git clone https://github.com/brainiak/rtAttenPenn.git
else
    echo "Directory rtAttenPenn already exists, skipping git clone"
fi
cd rtAttenPenn/
if [ ! -e "conda_environment.yml" ]; then
    echo "Missing conda_environment.yml file"
    exit -1;
fi
conda env create -f conda_environment.yml
conda activate rtAtten
python setup.py build_ext --inplace
cd certs
rm rtfMRI*
randNum=$RANDOM
openssl req -newkey rsa:2048 -nodes -keyout rtfMRI_rsa-$randNum.private -x509 -days 365 -out rtfMRI-$randNum.crt \
  -subj "/C=US/ST=New Jersey/L=Princeton/O=Princeton University/CN=rtAtten"; \
ln -s rtfMRI_rsa-$randNum.private rtfMRI_rsa.private; \
ln -s rtfMRI-$randNum.crt rtfMRI.crt
cd ..

# For Server Only
# echo "START SERVER"
# sudo iptables -I INPUT 8 -p tcp -s $clientAddr/16 --dport $servicePort -j ACCEPT
# python ServerMain.py -p $servicePort

# For Client Only
# echo "START CLIENT"
# scp $serverAddr:~/rtAttenPenn/certs/rtfMRI.crt ./certs/rtfMRI.crt
# python ClientMain.py -e rtAttenPennCfg.toml -a $serverAddr -p $servicePort
