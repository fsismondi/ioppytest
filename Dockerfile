# temporary file for building docker images manually for the testing tool
FROM ubuntu:16.04
MAINTAINER federico.sismondi@inria.fr

RUN apt-get update -y -qq && apt-get -y -qq install python3-dev
RUN apt-get -y install build-essential
RUN apt-get -y install python3-setuptools
RUN	apt-get -y install python3-pip
RUN	apt-get -y install python-pip
RUN	apt-get -y install supervisor
RUN	apt-get -y install tcpdump
RUN apt-get -y install net-tools

ADD . /coap_testing_tool
ENV PATH="/coap_testing_tool:$PATH"
WORKDIR /coap_testing_tool

# HACK to avoid "cannot open shared object file: Permission denied" , see https://github.com/dotcloud/docker/issues/5490
RUN mv /usr/sbin/tcpdump /usr/bin/tcpdump

# install testing tool's python dependencies:
RUN make intstall-requirements

#RUN  groupadd -g 500 coap && useradd -u 500 -g 500 coap
#USER coap

EXPOSE 5671 5672

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "coap_testing_tool/docker.coap_testing_tool.conf"]

