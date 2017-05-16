# temporary file for building docker images manually for the testing tool
FROM ubuntu:16.04
MAINTAINER federico.sismondi@inria.fr

RUN apt-get update -y -qq && apt-get -y -qq install python3-dev
RUN apt-get -y install python3-setuptools
RUN	apt-get -y install python3-pip
RUN	apt-get -y install python-pip
#RUN	apt-get -y install supervisor
#RUN	apt-get -y install tcpdump
# for CoAP Server Californium (delete this when we start supporting IUT resources selection)
#RUN apt-get -y install default-jre

ADD . /coap_testing_tool
ENV PATH="/coap_testing_tool:$PATH"
#RUN echo $LANG
#ENV LANG=en_US.utf8
#RUN echo $PATH
#RUN ls /coap_testing_tool
WORKDIR /coap_testing_tool

#py2 requirements
RUN pip install -r coap_testing_tool/agent/requirements.txt

#py3 requirements
RUN pip3 install -r automated_IUTs/coap_client_coapthon/CoAPthon/requirements.txt
#RUN pip3 install -r coap_testing_tool/test_coordinator/requirements.txt
#RUN pip3 install -r coap_testing_tool/test_analysis_tool/requirements.txt
#RUN pip3 install -r coap_testing_tool/packet_router/requirements.txt
#RUN pip3 install -r coap_testing_tool/sniffer/requirements.txt
#RUN pip3 install -r coap_testing_tool/webserver/requirements.txt

#RUN  groupadd -g 500 coap && useradd -u 500 -g 500 coap
#USER coap

EXPOSE 5671 5672

# launch processes
CMD supervisord -c supervisor.conf
