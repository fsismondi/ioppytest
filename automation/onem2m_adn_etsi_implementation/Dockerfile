FROM ubuntu:16.04

RUN apt-get update
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

# requirement for californium
RUN apt-get -y install default-jre

ADD . /ioppytest
ENV PATH="/ioppytest:$PATH"
WORKDIR /ioppytest

# install aux ioppytest packages
RUN python -m pip install ioppytest-agent
RUN python3 -m pip install ioppytest-utils

# requirements on automated-iut python code
RUN python3 -m pip install -r automation/requirements.txt

# temp PATCH for avoiding https://github.com/celery/py-amqp/issues/191
RUN python3 -m pip install -Iv amqp==2.2.2
RUN python -m pip install -Iv amqp==2.2.2


EXPOSE 5671 5672


# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "automation/onem2m_adn_etsi_implementation/supervisor.conf"]
