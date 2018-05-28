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

ADD . /ioppytest
ENV PATH="/ioppytest:$PATH"
WORKDIR /ioppytest

#py2 requirements
RUN python -m pip install -r ioppytest/agent/requirements.txt

#py3 requierements
RUN python3 -m pip install pika

#RUN cp automated_IUTs/coap_server_californium/supervisor.conf supervisor.conf

# temp PATCH for avoiding https://github.com/celery/py-amqp/issues/191
RUN python3 -m pip install -Iv amqp==2.2.2
RUN python -m pip install -Iv amqp==2.2.2

EXPOSE 5671 5672

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "automated_IUTs/coap_server_californium/supervisor.conf"]