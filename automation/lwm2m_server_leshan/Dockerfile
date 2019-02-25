FROM ubuntu:16.04
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
RUN apt-get -y install iputils-ping
RUN apt-get -y -qq install make
RUN apt-get -y -qq install git


# upgrade pip
RUN python -m pip install --upgrade pip
RUN python3 -m pip install --upgrade pip

# requirement for leshan server 
RUN apt-get -y install default-jre

#requirement for leshan server trigger
RUN  apt-get update -yq \
    && apt-get install curl gnupg -yq \
    && curl -sL https://deb.nodesource.com/setup_8.x | bash \
    && apt-get install nodejs -yq
RUN npm install body-parser
RUN npm install request

ADD . /ioppytest
ENV PATH="/ioppytest:$PATH"
WORKDIR /ioppytest

# install aux ioppytest packages
RUN python -m pip install ioppytest-agent
RUN python3 -m pip install ioppytest-utils

# requirements on autoamted-iut python code
RUN python3 -m pip install -r automation/requirements.txt

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "automation/lwm2m_server_leshan/supervisor.conf"]
