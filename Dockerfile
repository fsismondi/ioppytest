FROM ubuntu:16.04
#update software repo and install python3
RUN  apt-get update -y -qq && apt-get -y -qq install python3-dev git
RUN	apt-get -y install python3-pip
ADD . /coap_testing_tool
ENV PATH="/coap_testing_tool:$PATH"
RUN echo $LANG
#ENV LANG=en_US.utf8
RUN echo $PATH
RUN ls
RUN ls /coap_testing_tool
WORKDIR /coap_testing_tool

#requirements for coordinator
RUN pip3 install -r coap_testing_tool/test_coordinator/requirements.txt


RUN  groupadd -g 500 coap && useradd -u 500 -g 500 coap
USER coap

EXPOSE 80 5671 5672
 # run the API 
#CMD [ "python3","test.py" ]
#CMD python3 -m coap_testing_tool.test

#CMD python3 -m coap_testing_tool.test_coordinator.test
CMD python3 -m coap_testing_tool.test_coordinator.coordinator
