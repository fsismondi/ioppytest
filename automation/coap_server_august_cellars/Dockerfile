FROM mono:latest
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
RUN apt-get -y install iputils-ping
RUN apt-get -y -qq install make
RUN apt-get -y install git

# upgrade pip
RUN python -m pip install --upgrade pip
RUN python3 -m pip install --upgrade pip

# install aux ioppytest packages
RUN python -m pip install ioppytest-agent
RUN python3 -m pip install ioppytest-utils

## get ioppytest code for automating the IUT: either from local source code (option1), or from git (option2)

# option1) This is for the case Dockerfile is used from within ioppytest project
ADD . /ioppytest
ENV PATH="/ioppytest:$PATH"

# option2)This is for the case Dockerfile is used standalone ()
#RUN git clone https://gitlab.f-interop.eu/f-interop-contributors/ioppytest.git -b develop --single-branch /ioppytest

# requirements on automated-iut python code
RUN python3 -m pip install -r /ioppytest/automation/requirements.txt

ENV PATH="/ioppytest:$PATH"

# download and build august cellars coap server
RUN git clone https://github.com/Com-AugustCellars/TestServer /AugustCellarsTestServer
WORKDIR /AugustCellarsTestServer

# build implementation
RUN curl -L -o nuget.exe https://dist.nuget.org/win-x86-commandline/latest/nuget.exe
RUN mono nuget.exe restore TestServer.Net462.sln
RUN msbuild /p:Configuration=Debug TestServer.Net462.sln

# run implementation
#ENTRYPOINT mono /AugustCellarsTestServer/TestServer/bin/Debug/TestServer.exe --ipaddress=127.0.0.1 --interop-test=CoapCore

# temp PATCH for avoiding https://github.com/celery/py-amqp/issues/191
RUN python -m pip install -Iv amqp==2.3.1

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "/ioppytest/automation/coap_server_august_cellars/supervisor.docker.ini"]