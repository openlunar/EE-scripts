#!/bin/bash

apt-get install -y python3 python3-pip jupyter-core jupyter-notebook python3-notebook
apt-get install -y wget automake libtool libreadline-dev

cp patchfile /tmp/patchfile
cd /tmp
wget "https://downloads.sourceforge.net/project/ngspice/ng-spice-rework/30/ngspice-30.tar.gz"
tar -xzf ngspice-30.tar.gz
cd ngspice-30
./autogen.sh
./configure --enable-xspice --enable-cider --disable-debug \
	--with-readline=yes --with-ngshared \
	CFLAGS="-m64 -O2" LDFLAGS="-m64 -s"
make clean
patch src/frontend/cpitf.c </tmp/patchfile
make -j4
make install

export LD_LIBRARY_PATH /usr/local/lib

pip3 install PySpice valispace
