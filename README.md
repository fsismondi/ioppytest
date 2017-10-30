CoAP Testing Tool:
------------------

This repo contains all necessary software (and their dependencies) for running a
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

### Attention with the git submodules!

remember when cloning a project with submodules to use --recursive flag
```
git clone --recursive ...
```

or else (in case you forgot about the flag), right after cloning you can:
```
git submodule update --init --recursive
```

whenever you find that your utils libraries are not the latests versions
you can 'bring' those last changes from the main utils repo to your project
with:
```
git submodule update --remote --merge
```

after bringing the last changes you can update your project with the last changes by doing:
```
git add <someSubModuleDir>
git commit -m 'updated submodule reference to last commit'
git push
```

### Running CoAP testing tool as standalone mode

(# TODO talk about the CLI, without it you cannot run a session)

First thing needed is to have the rabbit running ;)
For this, you need a server running RabbitMQ message broker for handling the
messaging between the components taking part in your test session.

The options for this are:

- install locally RabbitMQ message broker on local machine,
create RMQ vhost, user, pass on local machine

    (# TODO add instructions)

- Request a remote vhost and its user, pass credentials to F-Interop developers.

    for this contact federico.sismondi@inria.fr or remy.leone@inria.fr

after having a created vhost with its user/password,
export in the machine where the testing tool is running the following
env vars:

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

#### Opt 1 - Building & running CoAP testing tool with docker (recommended)

First, let's install docker. For this just follow this instructions:

https://docs.docker.com/engine/installation/

Don't forget to start it!

Second, **build** the testing tool, from inside coap_testing_tool dir run:
```
make docker-build-all # build all tools, TT and automated-iuts
```

or run the docker build manually

```
docker build -t testing_tool-interoperability-coap .
```

for running the coap-testing-tool do
```
make run-coap-testing-tool
```

for verifying that TT is actually running:
```
make get-logs
```

Also, if you are running a session alone (no 2nd user) then you may
want to use one of the automated-iut or reference implementations,
for this, if you are testing your coap server:

```
make run-coap-client
```

or (if you are testing your coap client)
```
run-coap-server
```


If build fails due to a "Failed to fetch http://archive.ubuntu ...."
then:
```
docker build -t testing_tool-interoperability-coap . --no-cache
```

Go to FAQ, for known errors.

for running coap_testing_tool manually from docker api:

```
docker run -it
    --env AMQP_EXCHANGE=$AMQP_EXCHANGE
    --env AMQP_URL=$AMQP_URL
    --sysctl net.ipv6.conf.all.disable_ipv6=0
    --privileged
    testing_tool-interoperability-coap
```


alternatively, if you are curious and you want to know
what's under the hood:

```
docker run -it
    --env AMQP_EXCHANGE=$AMQP_EXCHANGE
    --env AMQP_URL=$AMQP_URL
    --sysctl net.ipv6.conf.all.disable_ipv6=0
    --privileged
    testing_tool-interoperability-coap
    bash

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
    -> try using --no-cache for the docker build
    -> more info http://stackoverflow.com/questions/24991136/docker-build-could-not-resolve-archive-ubuntu-com-apt-get-fails-to-install-a