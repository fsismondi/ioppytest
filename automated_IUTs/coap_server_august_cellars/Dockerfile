FROM mono:latest
MAINTAINER federico.sismondi@inria.fr

RUN apt-get update
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

# copying ioppytest code for automating the IUT
# `RUN git clone` instead of `ADD`, so this Dockerfile can be used "standalone"
# TODO put ioppytest in pypi and install as python package
RUN git clone https://gitlab.f-interop.eu/f-interop-contributors/ioppytest.git -b iut_august_cellars_automation --single-branch /ioppytest

ENV PATH="/ioppytest:$PATH"

# install aux ioppytest packages
RUN python -m pip install ioppytest-agent
RUN python3 -m pip install ioppytest-utils

# requirements on automated-iut python code
RUN python3 -m pip install -r /ioppytest/automated_IUTs/requirements.txt

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
RUN python -m pip install -Iv amqp==2.2.2

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "/ioppytest/automated_IUTs/coap_server_august_cellars/supervisor.docker.ini"]