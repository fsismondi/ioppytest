FROM node:10

# Create app directory
WORKDIR /usr/src/app

# Bundle app source
COPY . .

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
CMD [ "npm packages/cli/dist/cli.js examples/scripts/counter.js"]