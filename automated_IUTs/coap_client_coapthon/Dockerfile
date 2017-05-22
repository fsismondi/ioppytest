FROM ubuntu:16.04
MAINTAINER federico.sismondi@inria.fr

# docker build -t automated-iut-coap-client-coapthon-v01 ./coap_testing_tool/automated_implementations/coap_client_coapthon/

RUN apt-get update -y -qq && apt-get -y -qq install python3-dev
RUN apt-get -y install python3-setuptools
RUN	apt-get -y install python3-pip
RUN	apt-get -y install python-pip
RUN	apt-get -y install supervisor
RUN apt-get -y install iputils-ping

ADD . /coap_testing_tool
ENV PATH="/coap_testing_tool:$PATH"
WORKDIR /coap_testing_tool

#py2 requirements
RUN pip install -r coap_testing_tool/agent/requirements.txt

#py3 requirements
RUN pip3 install -r automated_IUTs/coap_client_coapthon/CoAPthon/requirements.txt
RUN pip3 install -r automated_IUTs/coap_client_coapthon/requirements.txt

EXPOSE 5671 5672

# launch processes
CMD supervisord --nodaemon --configuration automated_IUTs/coap_client_coapthon/supervisor.conf