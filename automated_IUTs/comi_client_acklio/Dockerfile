FROM ubuntu:16.04
MAINTAINER tanguy.ropitault@gmail.com

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

ADD . /ioppytest
ENV PATH="/ioppytest:$PATH"
WORKDIR /ioppytest

#py2 requirements
RUN python -m pip install -r ioppytest/agent/requirements.txt

# requirements on autoamted-iut python code
RUN python3 -m pip install -r automated_IUTs/requirements.txt

# CoMI binary and examples
#ADD automated_IUTs/comi_server_acklio/serverComi /CoMI/
#ADD automated_IUTs/comi_server_acklio/examples /CoMI/examples/


# temp PATCH for avoiding https://github.com/celery/py-amqp/issues/191
RUN python3 -m pip install -Iv amqp==2.2.2
RUN python -m pip install -Iv amqp==2.2.2

EXPOSE 5683

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "automated_IUTs/comi_client_acklio/supervisor.conf.ini"]


