CoAP Testing Tool:
------------------

This repo conaints all necessary software (and their dependencies) for running a 
CoAP interoperability test session.

This can be run as standalone software and also integrated to f-interop 
architecture.

### TODO
- add feat for handling step by step analysis
- document isntallation of requirements and dependencies

### CoAP Testing tools components

The CoAP testing tool handles the coordination, sniffing, dissection
and analysis of traces for the tests described in the test description.
The implemented test description is based on:
[ETSI CoAP test description](http://www.etsi.org/plugtests/CoAP/Document/CoAP_TestDescriptions_v015.pdf)

For description of components please visit: [f-interop doc](doc.f-interop.eu)


-----------------------------------------------------------------------------

### Clonning the project
```
git clone --recursive https://gitlab.f-interop.eu/fsismondi/coap_testing_tool.git
cd coap_testing_tool
```

### Running CoAP testing tool as standalone mode

(# TODO talk about the CLI, without it you cannot run a session)

First thing needed is to have the rabbit running ;)
You need a server running RabbitMQ message broker for handling the
messaging between the components taking part in your test session.

The options for this are:

- install locally RabbitMQ message broker on local machine,
create RMQ vhost, user, pass on local machine

    (# TODO add instructions)

- Request a remote vhost and its user, pass credentials to F-Interop developers.

    for this contact federico.sismondi@inria.fr or remy.leone@inria.fr

then, export in the machine where the testing tool is running the following vars:

    ```
    export AMQP_URL='amqp://someUser:somePassword@server/amqp_vhost'
    export AMQP_EXCHANGE='amq.topic'
    ```

---
#### Building & running the tool
Now, let's get the testing tool running. Several approaches can be used,
these are:

( tested with debian based OS & macos )

**1.** Build the testing tool using docker (see Dockerfile) &
run the testing tool inside a docker container (recommended)

**2.** Install dependencies with ansible in the local machine &
run the testing tool using supervisor.
(no agent can be run in the same machine after)

**3.** Install dependencies with ansible in remote machine &
run the testing tool using supervisor.

**4.** Install everything manually, why not right?

---

#### Opt 1 - Building & running CoAP testing tool with docker

First, let's install docker. For this just follow this instructions:

https://docs.docker.com/engine/installation/

Don't forget to start it!

Second, **build** the testing tool, from inside coap_testing_tool dir run:
```
docker build -t finterop-coap .
```

If build fails due to a "Failed to fetch http://archive.ubuntu ...."
then:
```
docker build -t finterop-coap . --no-cache
```

Go to FAQ, for known errors.

Finally, **run** it, from inside coap_testing_tool run:

```
docker run -it
    --env AMQP_EXCHANGE='default'
    --env AMQP_URL='amqp://someUser:somePassword@server/amqp_vhost'
    --privileged finterop-coap supervisord
    --nodaemon
    --configuration supervisor.conf
```

alternatively, you can:

```
docker run -it --env AMQP_EXCHANGE=default --env AMQP_URL='amqp://someUser:somePassword@server/amqp_vhost' --privileged finterop-coap  bash
root@bab3b2220510:/coap_testing_tool# supervisord -c supervisor.conf
root@bab3b2220510:/coap_testing_tool# supervisorctl -c supervisor.conf
agent                            RUNNING   pid 28, uptime 0:00:02
automated-iut                    STARTING
bootstrap-agent-TT               RUNNING   pid 19, uptime 0:00:02
packet-router                    RUNNING   pid 24, uptime 0:00:02
packet-sniffer                   RUNNING   pid 18, uptime 0:00:02
tat                              RUNNING   pid 17, uptime 0:00:02
test-coordinator                 RUNNING   pid 26, uptime 0:00:02
supervisor>
```

Run the CLI & Agent and you are ready to launch CoAP tests from your PC!


#### Opt 2 & 3 - Build CoAP testing tool with ansible


First thing, install ansible:

http://docs.ansible.com/ansible/intro_installation.html


Install supervisor (needed for spawning and monitoring processes):
For this follow this instructions:

http://supervisord.org/installing.html

  
Now, let's install the testing tool requirements:

**for Opt 2 (local install)**:

- change in ansible/main.yml the variable unix_user from f-interop to your
unix user, then run ansible script:

    ```
    ansible-playbook -i ansible/hosts.local ansible/main.yml
        --ask-become-pass
    ```

- run CoAP testing tool and monitor processes
    
    ```
    sudo -E supervisord -c supervisor.conf
    sudo supervisorctl -c supervisor.conf
    ```
	note: use -E when launching supervisor process, it preserves the
	env vars

Run the CLI & Agent and you are ready to launch CoAP tests from your PC!

**for Opt 3 (remote install)**:

TDB

FAQ
---

- I have my own CoAP implementation, how can I add it as an
automated-IUT into CoAP Testing Tool

    **TBD**

- Docker build returns a "cannot fetch package" or a "cannot resolve .."

    http://stackoverflow.com/questions/24991136/docker-build-could-not-resolve-archive-ubuntu-com-apt-get-fails-to-install-a