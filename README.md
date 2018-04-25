ioppytest framework:
--------------------

ioppytest is a framework for running interoperability tests.

This initial version tackles technical interoperability testing (CoAP
and 6LoWPAN interop tests), and effort is being made to implement
interop semantic tests notably for running tests in the WoT and OneM2M
context.

This repo contains all necessary software (and their dependencies) for
running a interoperability test sessions between two implementations
under test (IUT).

This can be run as standalone software and also integrated to f-interop
architecture.


Implemented test suites in the ioppytest framework:
---------------------------------------------------

The test suites implemented which are currently supported by the
framework are:

- CoAP Test Suite (user's IUT vs automated-IUT)
- CoAP Test Suite (between two users' IUT)
- 6LoWPAN Test Suite (between two users' IUT) (WIP)



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

[CORE API doc](http://doc.f-interop.eu/interop/)
and
[interop tests API doc](http://doc.f-interop.eu/interop/)



Running a test suite:
---------------------

user needs :

- an implementation under test (IUT) of a standard supported/protocol
by ioppytest framework, which either runs in some specific hardware or
locally in user's PC, e.g. a coap client implementation
-  run
[the agent component](http://doc.f-interop.eu/interop/#agent)
which will route all the packets emitted from the IUT to the backend
and also to the second IUT (and viceversa)
- a user interface to help coordinating the tests
(either GUI or CLI component)

For simplifying the access to CLI, agent and other components, ioppytest
inlcudes a Makefile, with it you can use `make cmd`,
for more information execute `make help`

# Running a test suite using F-Interop platform

go to [go.f-interop.eu](go.f-interop.eu) and follow the instructions

# Running a test suite standalone

This mode of execution work for any of the following circumstances

- user controls one IUT and wants to run tests against one of the
automated-IUTs the framework supports
- user controls one IUT and is in direct contact with a second user
controlling a second IUT
- user controls both implementations (IUTs) taking part in the interop
session

## Set up up the message broker

The interop testing tool use AMQP for sending messages between its
components, and the remote ones (like the agent). When running a
standalone setup the user first needs to have a RMQ broker running..

RMQ broker is a component which is **external** to the testing tool
and which establish the session and infrastructure so compomnents can
communicate with each other during the test session.

The options for this are:

- install locally RabbitMQ message broker on local machine,
create RMQ vhost, user, pass on local machine

    (# TODO add instructions)

- Request a remote vhost and credentials (user,pass) to
federico.sismondi@inria.fr (recommended)

don't hesitate to contact me, this is a very simple procedure and it's
free :D

## Export AMQP environment variables

after having a created vhost with its user/password,
export in the machine where the testing tool is running the following
env vars:

```
export AMQP_URL='amqp://someUser:somePassword@server/amqp_vhost'
export AMQP_EXCHANGE='amq.topic'
```

## Download the source code (see `Clonning the project` for more info)
```
git clone --recursive https://gitlab.f-interop.eu/f-interop-contributors/ioppytest.git
cd ioppytest
```


## Build the testing tools

(docker, py2 and py3 needs to be installed in the machine)
```
make build-all
```

## Run testing tool (CoAP testing tool example)
```
make run-coap-testing-tool
```

## Connect to the interop session using the CLI
```
make run-cli
```

## Connect the agent to the backend

if user's IUT is a CoAP client:

```
make run-agent-coap-client
```

if user's IUT is a CoAP server:

```
make run-agent-coap-server
```

## Running a second IUT

### User to user session, second user with his/her own IUT

The second IUT needs to connect to the same VHOST the same way first IUT
did. For this the RMQ broker needs to be reachable by this second IUT
 (and it's agent instance).

If this is the case then user 2 should just export the same environment
 variables as user 1, and launch agent, and CLI just as user 1 did.

### Single user session, against an automated-IUT

 If the user wants to run test against one of the automated-IUT
 (~reference implementation) supported by ioppytest:

```
make run-coap-server
```

or for a coap client automated implementation:

```
make run-coap-client
```


## Running the interop session

Simply follow the CLI instructions and enjoy! :)


The implemented tests are based on this specification:
[ETSI CoAP test description](http://www.etsi.org/plugtests/CoAP/Document/CoAP_TestDescriptions_v015.pdf)


Developping a new test suite:
-----------------------------

## Clonning the project
```
git clone --recursive https://gitlab.f-interop.eu/f-interop-contributors/ioppytest.git
cd ioppytest
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
what's under the hood:

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
env vars


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

    please contact federico.sismondi@inria.fr


- Docker build returns a "cannot fetch package" or a "cannot resolve .."

    try using ```--no-cache``` for the docker build

    more info http://stackoverflow.com/questions/24991136/docker-build-could-not-resolve-archive-ubuntu-com-apt-get-fails-to-install-a