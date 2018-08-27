FROM ubuntu:16.04
MAINTAINER tanguy.ropitault@gmail.com

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
RUN apt-get -y install iputils-ping
RUN apt-get -y -qq install make

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

# CoMI binary and examples
ADD automation/comi_server_acklio/serverComi /CoMI/
RUN chmod +x /CoMI/serverComi
ADD automation/comi_server_acklio/interop /CoMI/interop/

## temp PATCH for avoiding https://github.com/celery/py-amqp/issues/191
#RUN python3 -m pip install -Iv amqp==2.3.1
#RUN python -m pip install -Iv amqp==2.3.1

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "automation/comi_server_acklio/supervisor.conf.ini"]


