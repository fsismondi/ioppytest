# temporary file for building docker images manually for the testing tool
FROM ubuntu:16.04
MAINTAINER federico.sismondi@inria.fr

RUN apt-get update -y -qq && apt-get -y -qq install python-dev
RUN	apt-get -y install python-pip
RUN	apt-get -y install supervisor
# for CoAP Server Californium (delete this when we start supporting IUT resources selection)
RUN apt-get -y install default-jre

ADD . /coap_testing_tool
ENV PATH="/coap_testing_tool:$PATH"
WORKDIR /coap_testing_tool

#py2 requirements
RUN pip install -r coap_testing_tool/agent/requirements.txt



#RUN  groupadd -g 500 coap && useradd -u 500 -g 500 coap
#USER coap

EXPOSE 5671 5672

# launch processes
CMD supervisord -c automated_IUTs/coap_server_californium/supervisor.conf
