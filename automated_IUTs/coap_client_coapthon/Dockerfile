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

ADD . /coap_testing_tool
ENV PATH="/coap_testing_tool:$PATH"
WORKDIR /coap_testing_tool

#py2 requirements
RUN python -m pip install -r coap_testing_tool/agent/requirements.txt

#py3 requirements
RUN python3 -m pip install -r automated_IUTs/coap_client_coapthon/CoAPthon/requirements.txt
RUN python3 -m pip install -r automated_IUTs/coap_client_coapthon/requirements.txt

#RUN cp automated_IUTs/coap_client_coapthon/supervisor.conf supervisor.conf

EXPOSE 5671 5672

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "automated_IUTs/coap_client_coapthon/supervisor.conf"]