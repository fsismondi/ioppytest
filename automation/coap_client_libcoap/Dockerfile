FROM ubuntu:17.10
MAINTAINER federico.sismondi@inria.fr

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get -y -qq update
RUN apt-get -y -qq install apt-utils
RUN apt-get -y -qq install python3-dev
RUN apt-get -y -qq install build-essential
RUN apt-get -y -qq install python3-setuptools
RUN	apt-get -y -qq install python3-pip
RUN	apt-get -y -qq install python-pip
RUN	apt-get -y -qq install supervisor
RUN apt-get -y -qq install net-tools
RUN apt-get -y -qq install iputils-ping
RUN apt-get -y -qq install make
RUN apt-get -y -qq install wget
RUN apt-get -y -qq install git

# needed for ubuntu 17 or + for running <ip> commands
RUN apt-get -y -qq install iproute2

# upgrade pip
RUN python -m pip install --upgrade pip
RUN python3 -m pip install --upgrade pip

# install aux ioppytest packages
RUN python -m pip install ioppytest-agent
RUN python3 -m pip install ioppytest-utils

ADD . /ioppytest
ENV PATH="/ioppytest:$PATH"
WORKDIR /ioppytest

# requirements on automated-iut python code
RUN python3 -m pip install -r automation/requirements.txt

# Install autogen dependencies
RUN apt-get -y install autoconf
RUN apt-get -y install pkg-config
RUN apt-get -y install libtool
RUN apt-get -y install autotools-dev
RUN apt-get -y install automake

# Install libcoap API & CLI from sources
RUN mkdir automation/coap_client_libcoap/libcoap
WORKDIR /ioppytest/automation/coap_client_libcoap/libcoap
RUN git init
RUN git clone https://github.com/obgm/libcoap.git
WORKDIR /ioppytest/automation/coap_client_libcoap/libcoap/libcoap

RUN ./autogen.sh
RUN ./configure --enable-examples --disable-doxygen --disable-manpages
RUN make
RUN make install
ENV PATH="/ioppytest/automation/coap_client_libcoap/libcoap/libcoap/examples:$PATH"

## temp PATCH for avoiding https://github.com/celery/py-amqp/issues/191
#RUN python3 -m pip install -Iv amqp==2.3.1
#RUN python -m pip install -Iv amqp==2.3.1

WORKDIR /ioppytest

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "automation/coap_client_libcoap/supervisor.conf"]
