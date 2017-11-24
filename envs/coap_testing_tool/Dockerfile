FROM ubuntu:16.04
MAINTAINER federico.sismondi@inria.fr

RUN apt-get update -y -qq
RUN apt-get -y -qq install python3-dev
RUN apt-get -y -qq install build-essential
RUN apt-get -y -qq install python3-setuptools
RUN	apt-get -y -qq install python3-pip
RUN	apt-get -y -qq install python-pip
RUN	apt-get -y -qq install supervisor
RUN	apt-get -y -qq install tcpdump
RUN apt-get -y -qq install net-tools

# upgrade pip
RUN python -m pip install --upgrade pip
RUN python3 -m pip install --upgrade pip

ADD . /coap_testing_tool
ENV PATH="/coap_testing_tool:$PATH"
WORKDIR /coap_testing_tool

# HACK to avoid "cannot open shared object file: Permission denied" , see https://github.com/dotcloud/docker/issues/5490
RUN mv /usr/sbin/tcpdump /usr/bin/tcpdump

#installing py2 dependencies
RUN python -m pip install -r coap_testing_tool/agent/requirements.txt --upgrade

#installing py3 dependencies
RUN python3 -m pip install -r coap_testing_tool/test_coordinator/requirements.txt --upgrade
RUN python3 -m pip install -r coap_testing_tool/test_analysis_tool/requirements.txt --upgrade
RUN python3 -m pip install -r coap_testing_tool/packet_router/requirements.txt --upgrade
RUN python3 -m pip install -r coap_testing_tool/sniffer/requirements.txt --upgrade
RUN python3 -m pip install -r coap_testing_tool/webserver/requirements.txt --upgrade

#RUN  groupadd -g 500 coap && useradd -u 500 -g 500 coap
#USER coap

EXPOSE 5671 5672

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "envs/coap_testing_tool/supervisor.docker.conf.ini"]
