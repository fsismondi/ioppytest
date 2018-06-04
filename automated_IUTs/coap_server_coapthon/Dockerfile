FROM ubuntu:16.04
MAINTAINER federico.sismondi@inria.fr

RUN apt-get update -y -qq && apt-get -y -qq install python3-dev
RUN apt-get -y install python3-setuptools
RUN	apt-get -y install python3-pip
RUN	apt-get -y install python-pip
RUN	apt-get -y install supervisor
RUN apt-get -y install iputils-ping
RUN apt-get -y install net-tools

# upgrade pip
RUN python -m pip install --upgrade pip
RUN python3 -m pip install --upgrade pip

ADD . /ioppytest
ENV PATH="/ioppytest:$PATH"
WORKDIR /ioppytest

#py2 requirements
RUN python -m pip install -r ioppytest/agent/requirements.txt

#py3 requirements
RUN python3 -m pip install -r automated_IUTs/coap_server_coapthon/CoAPthon/requirements.txt

# requirements on autoamted-iut python code
RUN python3 -m pip install -r automated_IUTs/requirements.txt

RUN cp automated_IUTs/coap_server_coapthon/supervisor.conf supervisor.conf

# temp PATCH for avoiding https://github.com/celery/py-amqp/issues/191
RUN python3 -m pip install -Iv amqp==2.2.2
RUN python -m pip install -Iv amqp==2.2.2

EXPOSE 5671 5672

# launch processes
CMD supervisord --nodaemon --configuration supervisor.conf