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

# Install libcoap API
RUN apt-get -y install libcoap-1-0

# Install libcoap CLI
RUN apt-get -y install libcoap-1-0-bin

# upgrade pip
RUN python -m pip install --upgrade pip
RUN python3 -m pip install --upgrade pip

ADD . /ioppytest
ENV PATH="/ioppytest:$PATH"
WORKDIR /ioppytest

RUN mkdir automated_IUTs/coap_client_libcoap/file
RUN wget https://raw.githubusercontent.com/obgm/libcoap/develop/examples/etsi_iot_01_largedata.txt -P automated_IUTs/coap_client_libcoap/file

# requirements on automated-iut python code
RUN python3 -m pip install -r automated_IUTs/requirements.txt

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "automated_IUTs/coap_client_libcoap/supervisor.conf"]
