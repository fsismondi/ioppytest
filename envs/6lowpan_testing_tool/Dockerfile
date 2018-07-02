FROM ubuntu:16.04
MAINTAINER federico.sismondi@inria.fr

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update
RUN apt-get -y -qq install apt-utils
RUN apt-get -y -qq install python3-dev
RUN apt-get -y -qq install build-essential
RUN apt-get -y -qq install python3-setuptools
RUN	apt-get -y -qq install python3-pip
RUN	apt-get -y -qq install supervisor
RUN	apt-get -y -qq install tcpdump
RUN apt-get -y -qq install net-tools

# upgrade pip
RUN python3 -m pip install --upgrade pip

ADD . /ioppytest
ENV PATH="/ioppytest:$PATH"
WORKDIR /ioppytest

#installing py3 dependencies
RUN python3 -m pip install -r ioppytest/test_coordinator/requirements.txt --upgrade
RUN python3 -m pip install -r ioppytest/test_analysis_tool/requirements.txt --upgrade
RUN python3 -m pip install -r ioppytest/packet_router/requirements.txt --upgrade
RUN python3 -m pip install -r ioppytest/packet_sniffer/requirements.txt --upgrade
RUN python3 -m pip install -r ioppytest/webserver/requirements.txt --upgrade
RUN python3 -m pip install -r ioppytest/utils/requirements.txt

#RUN  groupadd -g 500 coap && useradd -u 500 -g 500 coap
#USER coap

# temp PATCH for avoiding https://github.com/celery/py-amqp/issues/191
RUN python3 -m pip install -Iv amqp==2.2.2

EXPOSE 5671 5672

CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "envs/6lowpan_testing_tool/supervisor.docker.conf.ini"]