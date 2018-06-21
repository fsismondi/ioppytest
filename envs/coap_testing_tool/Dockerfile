FROM ubuntu:16.04
MAINTAINER federico.sismondi@inria.fr

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update
RUN apt-get -y -qq install apt-utils
RUN apt-get -y -qq install python3-dev
RUN apt-get -y -qq install build-essential
RUN apt-get -y -qq install python3-setuptools
RUN	apt-get -y -qq install python3-pip
RUN	apt-get -y -qq install python-pip
RUN	apt-get -y -qq install supervisor
RUN apt-get -y -qq install net-tools
RUN apt-get -y -qq install make

#RUN	apt-get -y -qq install tcpdump
## HACK to avoid "cannot open shared object file: Permission denied" , see https://github.com/dotcloud/docker/issues/5490
#RUN mv /usr/sbin/tcpdump /usr/bin/tcpdump


# upgrade pip
RUN python -m pip install --upgrade pip
RUN python3 -m pip install --upgrade pip

ADD . /ioppytest
ENV PATH="/ioppytest:$PATH"
WORKDIR /ioppytest



#installing py2 dependencies
RUN python -m pip install -r ioppytest/agent/requirements.txt --upgrade

# Makefile entrypoint
RUN make install-python-dependencies

#RUN  groupadd -g 500 coap && useradd -u 500 -g 500 coap
#USER coap

# temp PATCH for avoiding https://github.com/celery/py-amqp/issues/191
RUN python3 -m pip install -Iv amqp==2.2.2
RUN python -m pip install -Iv amqp==2.2.2

EXPOSE 5671 5672

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "envs/coap_testing_tool/supervisor.docker.conf.ini"]
