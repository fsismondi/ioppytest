FROM node:10

# Create app directory
WORKDIR /usr/src/app

# Bundle app source
# COPY . .

# ioppytest standard docker build procedure:
RUN apt-get -y -qq update
RUN apt-get -y -qq install apt-utils
RUN apt-get -y -qq install python3-dev
RUN apt-get -y -qq install build-essential
RUN apt-get -y -qq install python3-setuptools
RUN apt-get -y -qq install python3-pip
RUN apt-get -y -qq install python-pip
RUN apt-get -y -qq install supervisor
RUN apt-get -y -qq install net-tools
RUN apt-get -y install iputils-ping
RUN apt-get -y -qq install make

# upgrade pip
RUN python -m pip install --upgrade pip
RUN python3 -m pip install --upgrade pip

# install aux ioppytest packages
RUN python -m pip install ioppytest-agent
RUN python3 -m pip install ioppytest-utils


# node-wot install procedure :
RUN git clone https://github.com/eclipse/thingweb.node-wot
WORKDIR thingweb.node-wot
RUN npm install
#RUN curl -sL https://deb.nodesource.com/setup_10.x | sudo -E bash -
#RUN apt-get install -y nodejs
#RUN npm install

# If you are building your code for production
# RUN npm install --only=production
RUN npm run build

EXPOSE 8080
#CMD [ "node", "packages/cli/dist/cli.js", "examples/scripts/counter.js"]

# copy supervisor processes configs
ADD automation/wot_thingweb/supervisor.conf.ini supervisor.conf.ini

# launch processes
CMD ["/usr/bin/supervisord", "--nodaemon", "--configuration", "supervisor.conf.ini"]
