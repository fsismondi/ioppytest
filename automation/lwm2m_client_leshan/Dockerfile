FROM ubuntu:16.04
MAINTAINER federico.sismondi@inria.fr

RUN apt-get update -y -qq && apt-get -y -qq install python-dev
RUN	apt-get -y install python-pip
RUN apt-get -y -qq install python3-dev
RUN apt-get -y install python3-setuptools
RUN	apt-get -y install python3-pip
RUN	apt-get -y install supervisor
RUN apt-get -y install iputils-ping
RUN apt-get -y install net-tools

# upgrade pip
RUN python -m pip install --upgrade pip
RUN python3 -m pip install --upgrade pip

# requirement for californium
RUN apt-get -y install default-jre --fix-missing

# install aux ioppytest packages
RUN python -m pip install ioppytest-agent
RUN python3 -m pip install ioppytest-utils

ADD . /ioppytest
ENV PATH="/ioppytest:$PATH"
WORKDIR /ioppytest

# requirements on automated-iut python code
RUN python3 -m pip install -r automation/requirements.txt

## temp PATCH for avoiding https://github.com/celery/py-amqp/issues/191
#RUN python3 -m pip install -Iv amqp==2.3.1
#RUN python -m pip install -Iv amqp==2.3.1

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "automation/lwm2m_client_leshan/supervisor.conf"]
