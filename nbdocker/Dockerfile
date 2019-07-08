FROM ubuntu:19.10
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    wget \
    automake \
    libtool \
    libreadline-dev

RUN wget "https://downloads.sourceforge.net/project/ngspice/ng-spice-rework/30/ngspice-30.tar.gz"
RUN tar -xzf ngspice-30.tar.gz

WORKDIR ngspice-30
RUN ./autogen.sh
RUN ./configure --enable-xspice --enable-cider \
    --disable-debug --with-readline=yes --with-ngshared \
    CFLAGS="-m64 -O2" LDFLAGS="-m64 -s"
RUN make clean
COPY patchfile ./patchfile
RUN patch src/frontend/cpitf.c <patchfile
RUN make -j4
RUN make install
ENV LD_LIBRARY_PATH /usr/local/lib

RUN pip3 install \
    PySpice \
    jupyter \
    valispace

RUN useradd -m user

EXPOSE 8888
USER user
WORKDIR /home/user
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser"]
