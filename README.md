ioppytest framework:
--------------------

ioppytest is a framework for running interoperability tests.

This initial version tackles technical interoperability testing (CoAP,
 LwM2M, 6LoWPAN and OneM2M interop tests).

This repo contains all necessary software (and their dependencies) for
running a interoperability test sessions between two implementations
under test (IUT).

This can be run as standalone software and also integrated to f-interop
platform (go.f-interop.eu)


Implemented test suites in the ioppytest framework:
---------------------------------------------------

The test suites implemented which are currently supported by the
framework are:

- CoAP Test Suite (user's IUT vs automated-IUT)
- CoAP Test Suite (between two users' IUT)
- 6LoWPAN Test Suite (between two users' IUT) (WIP)
- LwM2M Test Suite (between two users' IUT) (WIP)
- oneM2M Test Suite (between two users' IUT) (WIP)



Test setup:
-----------

An interop session happens between two implementation under test (IUT),
the following diagram shows the setup including the IUTs, testing tool
and auxiliary components needed for running a interop session.

All interactions between components take place using the AMQP event bus
(AMQP pub/sub mechanism)

```
                    +----------------------------+             +----------------------------+             +----------------------------+
                    |                            |             |                            |             |                            |
                    |    ioppytest Test Tool     |             |     User Interface         |             |     User Interface         |
                    |(CoAP, 6LoWPAN, OneM2M, etc)|             |         (user 1)           |             |         (user 2)           |
                    |                            |             |                            |             |                            |
                    |                            |             |                            |             |                            |
                    +----------------------------+             +----------------------------+             +----------------------------+

                             ^    +                                     ^    +                                     ^    +
                             |    |                                     |    |                                     |    |
                             |    |                                     |    |                                     |    |
                             |    |                                     |    |                                     |    |
fromAgent.agent_x.tun.packet |    | toAgent.agent_y.tun.packet          |    |  ui.user1.step_verify.reply         |    |
                             |    |                                     |    |                                     |    |
fromAgent.agent_y.tun.packet |    | toAgent.agent_x.tun.packet          |    |                                     |    |
                             |    |                                     |    |                                     |    |
                             |    | ui.user1.step_verify.request        |    |                                     |    |
                             +    v                                     +    v                                     +    v

        +------------------------------------------------------------------------------------------------------------------------------------------------>
                                                                         AMQP Event Bus
        <-------------------------------------------------------------------------------------------------------------------------------------------------+

                                                       +     ^                                        +     ^
                                                       |     | toAgent.agent_x.tun.packetet           |     |  fromAgent.agent_y.tun.packet
                              data.tun.toAgent.agent_x |     |                                        |     |
                                                       |     |              toAgent.agent_y.tun.packet|     |
                                                       v     |                                        v     |
                                PC        +------------+-----+-------------+              +-----------+-----+--------------+
                                user 1    |                                |              |                                |
                                          |      Agent (agent_x)           |              |      Agent (agent_y)           |
                                          |        (tun mode)              |              |        (tun mode)              |
                                          |                                |              |                                |
                                          |                                |              |                                |
                                          | +-----+tun interface+-------+  |              | +-----+tun interface+-------+  |
                                          |                                |              |                                |
                                          | +----------------------------+ |              | +----------------------------+ |
                                          | |         IPv6+based         | |              | |         IPv6+based         | |
                                          | |        communicating       | |              | |        communicating       | |
                                          | |      piece of software     | |              | |      piece of software     | |
                                          | |      (e.g. coap client)    | |              | |      (e.g. coap server)    | |
                                          | |                            | |              | |                            | |
                                          | +----------------------------+ |              | +----------------------------+ |
                                          |                                |              |                                |
                                          +--------------------------------+              +--------------------------------+
```

Event Bus API:
--------------

All the calls between the components are documented here:

[interop tests API doc](http://doc.f-interop.eu/interop/)


Running a test suite:
---------------------

user needs :

- an implementation under test (IUT) of a standard supported/protocol
by ioppytest framework e.g. a coap client implementation
-  run
[the agent component](http://doc.f-interop.eu/interop/#agent)
which plays the role of a vpn-client , and which will route all the
packets sent from the IUT (on a certain ipv6 network) to the
backend -which is later on routed to second IUT (and viceversa)-.
- a user interface to help coordinating the tests
(either GUI or CLI component)

For simplifying the access to CLI, agent and other components, ioppytest
includes a Makefile, with it you can use `make <cmd>`,
for more information execute `make help`

### make commands

```
➜  ioppytest git:(master) ✗ make help
help:                          Help dialog.
build-all-coap-images:         Build all testing tool in docker images, and other docker image resources too
build-tools:                   builds all testing tool docker images (only testing tool)
build-automated-iuts:          Build all automated-iut docker images
build-all:                     Build all testing tool in docker images, and other docker image resources too
clean:                         clean data directory
sniff-bus:                     Listen and echo all messages in the event bus
run-cli:                       Run interactive shell
run-6lowpan-testing-tool:      Run 6LoWPAN testing tool in docker container
run-coap-testing-tool:         Run CoAP testing tool in docker container
run-lwm2m-testing-tool:        Run lwm2m testing tool in docker container
run-onem2m-testing-tool:       Run oneM2M testing tool in docker container
run-comi-testing-tool:         Run CoMI testing tool in docker container
stop-all:                      stops testing tools and IUTs running as docker containers
validate-test-description-syntax: validate (yaml) test description file syntax
run-tests:                     runs all unittests
get-logs:                      echoes logs from the running containers
install-python-dependencies:   installs all py2 and py3 pip dependencies
```

# Test session setups:

The supported setups are:

- user controls one IUT and wants to run tests against one of the
automated-IUTs the framework supports
- user controls one IUT and is in direct contact with a second user
controlling a second IUT
- user controls both implementations (IUTs) taking part in the interop
session

# (opt 1) Running a test suite using F-Interop platform

go to [go.f-interop.eu](go.f-interop.eu) and follow the instructions

Recommended option (more user friendly).

# (opt 2) Running a test suite standalone

for this, you will use ioppytest_cli  as CLI for
interfacing with testing tool (comms go over AMQP event bus).

Recommended option only for testing tool contributors.

## (opt 2.1) Set up up the message broker

The interop testing tool use RabbitMQ (RMQ) message broker for sending
messages between its components, and the remote ones (like the agent).

RMQ broker is a component which is **external** to the testing tool
and which establish the session and infrastructure so components can
communicate with each other during the test session.

If using [go.f-interop.eu](go.f-interop.eu) then this is automatically
set-up for you.

When running a standalone setup the user first needs to have a RMQ
broker running..

The options for this are:

- install locally RabbitMQ message broker on local machine,
create RMQ vhost, user, pass on local machine

    (# TODO add instructions)

- Request a remote vhost and credentials (user,pass) to
federico<dot>sismondi<at>inria<dot>fr (recommended)

don't hesitate to contact me, this is a very simple procedure and it's
free :D

## (opt 2.2) Export AMQP environment variables

after having a created vhost with its user/password,
export in the machine where the testing tool is running the following
env vars:

```
export AMQP_URL='amqp://someUser:somePassword@server/amqp_vhost'
export AMQP_EXCHANGE='amq.topic'
```

## (opt 2.3) Download the source code (see `Clonning the project` for more info)
```
git clone https://gitlab.f-interop.eu/f-interop-contributors/ioppytest.git
cd ioppytest
```


## (opt 2.4) Build the testing tools

(docker, py2 and py3 needs to be installed in the machine)
```
make build-all
```

## (opt 2.5) Run testing tool (CoAP testing tool example)
```
make run-coap-testing-tool
```

## (opt 2.6) Connect to the interop session using the CLI
```
make run-cli
```

## (opt 2.7) Connect the agent to the backend

if user's IUT is a CoAP client:

```
make run-agent-coap-client
```

if user's IUT is a CoAP server:

```
make run-agent-coap-server
```

## (opt 2.8) Running a second IUT

### (opt 2.8.1) User to user session, second user with his/her own IUT

The second IUT needs to connect to the same VHOST the same way first IUT
did. For this the RMQ broker needs to be reachable by this second IUT
 (and it's agent instance).

If this is the case then user 2 should just export the same environment
 variables as user 1, and launch agent, and CLI just as user 1 did.

### (opt 2.8.2) Single user session, against an automated-IUT

 If the user wants to run test against one of the automated-IUT
 (~reference implementation) supported by ioppytest:

```
make run-coap-server
```

or for a coap client automated implementation:

```
make run-coap-client
```


## (opt 2.9) Running the interop session

Simply follow the CLI instructions and enjoy! :)


The implemented tests are based on this specification:
[ETSI CoAP test description](http://www.etsi.org/plugtests/CoAP/Document/CoAP_TestDescriptions_v015.pdf)


Developping a new test suite:
-----------------------------

## Clonning the project
```
git clone https://gitlab.f-interop.eu/f-interop-contributors/ioppytest.git
cd ioppytest
```

## How to merge new features to upstream branch ?

Read CONTRIBUTING.rst document

## How can I develop & debug test suites?

for getting logs from the docker containers you can:
```
make get-logs
```

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
what's under the hood, you can see which processes are being run -in
the docker container- by the testing tool:

```
docker run -it
    --env AMQP_EXCHANGE=$AMQP_EXCHANGE
    --env AMQP_URL=$AMQP_URL
    --sysctl net.ipv6.conf.all.disable_ipv6=0
    --privileged
    testing_tool-interoperability-coap
    bash

root@bab3b2220510:/ioppytest# supervisord -c supervisor.conf
root@bab3b2220510:/ioppytest# supervisorctl -c supervisor.conf
agent                            RUNNING   pid 28, uptime 0:00:02
packet-router                    RUNNING   pid 24, uptime 0:00:02
packet-sniffer                   RUNNING   pid 18, uptime 0:00:02
tat                              RUNNING   pid 17, uptime 0:00:02
test-coordinator                 RUNNING   pid 26, uptime 0:00:02
supervisor>
```

or you can also run directly the processes without docker:
(supervisord needed)

```
sudo -E supervisord -c routeToConfigurationFileForTheTestSuite
sudo -E supervisorctl -c routeToConfigurationFileForTheTestSuite
```

you can use for example envs/coap_testing_tool/supervisor.conf.ini
for using the coap_testing_tool

note: use -E when launching supervisor process, it preserves the
env vars (like an exported AMQP_URL)


FAQ
---

- How can I install docker on my machine?

    For this just follow this instructions: https://docs.docker.com/engine/installation/


- How do I install supervisord on my machine?
    Install supervisor (needed for spawning and monitoring processes):
    For this follow this instructions:
    http://supervisord.org/installing.html

- I have my own CoAP implementation, how can I add it as an
automated-IUT into CoAP Testing Tool:

    please contact federico<dot>sismondi<at>inria<dot>fr


- Docker build returns a "cannot fetch package" or a "cannot resolve .."

    try using ```--no-cache``` for the docker build

    more info http://stackoverflow.com/questions/24991136/docker-build-could-not-resolve-archive-ubuntu-com-apt-get-fails-to-install-a