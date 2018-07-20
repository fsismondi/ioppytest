FROM ubuntu:17.10
MAINTAINER federico.sismondi@inria.fr

RUN apt-get update -y -qq && apt-get -y -qq install python3-dev
RUN apt-get -y install python3-setuptools
RUN	apt-get -y install python3-pip
RUN	apt-get -y install python-pip
RUN	apt-get -y install supervisor
RUN apt-get -y install iputils-ping
RUN apt-get -y install net-tools
RUN apt-get -y install wget

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

#py2 requirements
RUN python -m pip install -r ioppytest/agent/requirements.txt

EXPOSE 5671 5672

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "automated_IUTs/coap_client_libcoap/supervisor.conf"]
