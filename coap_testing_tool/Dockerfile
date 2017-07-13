# temporary file for building docker images manually for the testing tool
FROM ubuntu:16.04
MAINTAINER federico.sismondi@inria.fr

RUN apt-get update -y -qq && apt-get -y -qq install python3-dev
RUN apt-get -y install python3-setuptools
RUN	apt-get -y install python3-pip
RUN	apt-get -y install python-pip
RUN	apt-get -y install supervisor
RUN	apt-get -y install tcpdump
RUN apt-get -y install net-tools

ADD . /coap_testing_tool
ENV PATH="/coap_testing_tool:$PATH"
WORKDIR /coap_testing_tool/coap_testing_tool

#py2 requirements
RUN pip install -r agent/requirements.txt

#py3 requirements
RUN pip3 install -r test_coordinator/requirements.txt
RUN pip3 install -r test_analysis_tool/requirements.txt
RUN pip3 install -r packet_router/requirements.txt
RUN pip3 install -r sniffer/requirements.txt
RUN pip3 install -r webserver/requirements.txt


#RUN  groupadd -g 500 coap && useradd -u 500 -g 500 coap
#USER coap

EXPOSE 5671 5672

# launch processes
CMD supervisord --nodaemon --configuration  supervisord.conf
