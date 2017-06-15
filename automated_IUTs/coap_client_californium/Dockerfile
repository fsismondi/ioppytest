FROM ubuntu:16.04
MAINTAINER federico.sismondi@inria.fr

RUN apt-get update -y -qq && apt-get -y -qq install python3-dev
RUN apt-get -y install python3-setuptools
RUN	apt-get -y install python3-pip
RUN	apt-get -y install python-pip
RUN	apt-get -y install supervisor
RUN apt-get -y install iputils-ping
RUN apt-get -y install net-tools

# requirement for californium
RUN apt-get -y install default-jre

ADD . /coap_testing_tool
ENV PATH="/coap_testing_tool:$PATH"
WORKDIR /coap_testing_tool

#py2 requirements
RUN pip install -r coap_testing_tool/agent/requirements.txt

#py3 requierements
RUN pip3 install pika

RUN cp automated_IUTs/coap_client_californium/supervisor.conf supervisor.conf

EXPOSE 5671 5672

# launch processes
CMD supervisord --nodaemon --configuration supervisor.conf
