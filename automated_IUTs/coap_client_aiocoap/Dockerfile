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
RUN apt-get -y -qq install iputils-ping
RUN apt-get -y -qq install make

# upgrade pip
RUN python -m pip install --upgrade pip
RUN python3 -m pip install --upgrade pip

ADD . /ioppytest
ENV PATH="/ioppytest:$PATH"
WORKDIR /ioppytest

# install aux ioppytest packages
RUN python -m pip install ioppytest-agent
RUN python3 -m pip install ioppytest-utils

#py3 requirements
RUN python3 -m pip install -r automated_IUTs/coap_client_aiocoap/requirements.txt

#RUN cp automated_IUTs/coap_client_aiocoap/supervisor.conf supervisor.conf

EXPOSE 5671 5672

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "automated_IUTs/coap_client_aiocoap/supervisor.conf"]
