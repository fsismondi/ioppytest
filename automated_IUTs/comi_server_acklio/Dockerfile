FROM ubuntu:16.04
MAINTAINER tanguy.ropitault@gmail.com

RUN apt-get update && apt-get install -y --no-install-recommends apt-utils
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

#py3 requierements
RUN python3 -m pip install pika

# CoMI binary and examples
ADD automated_IUTs/comi_server_acklio/serverComi /CoMI/
RUN chmod +x /CoMI/serverComi
ADD automated_IUTs/comi_server_acklio/interop /CoMI/interop/


EXPOSE 5683

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "automated_IUTs/comi_server_acklio/supervisor.conf.ini"]


