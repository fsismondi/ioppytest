ioppytest framework:
--------------------

ioppytest is a framework for building interoperability testing tools.

This repo contains all necessary software (and their dependencies) for
running a interoperability test sessions between two implementations
under test (IUT).

Handles requirements coming from:

- interop testing best practises for network protocols
- distributed execution of the tests (IUTs may be in remote locations)
- test coordination between users (user-assisted test)
- driving automated IUTs, in a generic, program-language-agnostic way
- tunneling mechanism for enabling remote interop test over
distant locations and bypass middle-box.

Some of the features include:
tunneling, sniffing, test coordination, dissection, traces analysis,
test spec online server, etc. Each of these are independent python
modules, they communicate using json messages over AMQP.

For more about this check out the AMQP API defined in the `messages`
package which is installed with
(ioppytest-utils)*[https://pypi.org/project/ioppytest-utils/]:


Test suites
-----------

ioppytest includes interop test tools for:

- coap
- 6lowpan
- onem2m
- lwm2m

each ioppytest test suite is defined by config files found in `env/<test_suite_folder>` and `ioppytest/test_descriptions`

You can opt to disable some features by dissabling directy certain python processes. 
You can do this just by modifying `supervisor.conf.ini` in `env/<test_suite_folder>` directory.

How can I use it?
-------------------

You can either go to (F-Interop Platform)*[https://go.f-interop.eu]
which builds and deploys the tool automatically for you, this provides
also a nice looking web-based GUI (recommended).

Run in a stanalone, less user friendly way.
For this you will need to build some docker images, and set up of a RMQ server. 
User will then use a CLI for interfacing with the testin tool.

For more info about the standalone deployment, continue reading..

Implemented test suites in the ioppytest framework:
------------------------------------------------------------

The test suites implemented which are currently supported by the
framework are:

- CoAP Test Suite (user's IUT vs automated-IUT)
- CoAP Test Suite (between two users' IUT)
- 6LoWPAN Test Suite (between two users' IUT) (WIP)
- LwM2M Test Suite (between two users' IUT) (WIP)
- oneM2M Test Suite (between two users' IUT) (WIP)

Test setup:
------------

An interoperability test happens between two `implementation under test (IUT)`.
Each IUT is normally "driven" by a different user, each user normally makes use of a `UI` for following the test procedure.
Each IUT sends IP packets using the `TUN interface` (virutal interface), which is created by the `agent` component.

The following diagram shows what the interop test setup used when using `ioppytest`.  
Component of the setup interact with each other using the `AMQP event bus` (AMQP pub/sub mechanism), routing keys/topics used for these intereactions are documented below.

```
                                      +----------------------------+
                                      |                            |
                                      |    ioppytest Test Tool     |
                                      |(CoAP, 6LoWPAN, OneM2M, etc)|
                                      |                            |
                                      |                            |
                                      +----------------------------+
                                                 ^    +
                                                 |    |
                                                 |    |
                                                 |    |
                         packet.fromAgent.agent_x|    |  packet.toAgent_agent_y
                                                 |    |
                         packet.fromAgent.agent_x|    |  packet.toAgent_agent_y
                                                 |    |
                         ui.user_1.reply         |    |  ui.user_1.request
                                                 +    v

+------------------------------------------------------------------------------------------------------------------------------------------------>
                                                                AMQP Event Bus
<-------------------------------------------------------------------------------------------------------------------------------------------------+
         |   ^                              ^  |                                           |   ^                              ^  |
         |   |     packet.fromAgent.agent_x |  | packet.toAgent_agent_x                    |   |     packet.fromAgent.agent_y |  | 
ui.user_1|   |                              |  |                                           |   |                              |  |
 .request|   | ui.user_1.reply              |  |                          ui.user_2.request|   | ui.user_2.reply              |  |
         |   |                              |  |                                           |   |                              |  |
         |   |                              |  v                                           |   |                              |  v
 +-------v-------------+      +--------------------------------+                   +-------v-------------+      +--------------------------------+
 |                     |      | +---------------------------+  |                   |                     |      | +---------------------------+  |
 |   User Interface    |      | |      Agent (agent_x)      |  |                   |   User Interface    |      | |      Agent (agent_y)      |  |
 |       (user 1)      |      | |        (tun mode)         |  |                   |       (user 2)      |      | |        (tun mode)         |  |
 |                     |      | +---------------------------+  |                   |                     |      | +---------------------------+  |
 +---------------------+      |                                |                   +---------------------+      |                                |
                              | +-----+tun interface+-------+  |                                                | +-----+tun interface+-------+  |
                              |                                |                                                |                                |
                              | +----------------------------+ |                                                | +----------------------------+ |
                              | | Implementation under test  | |                                                | | Implementation under test  | |
                              | |          using IP          | |                                                | |          using IP          | |
                              | |      (e.g. coapoclient)    | |                                                | |      (e.g. coaposerver)    | |
                              | +----------------------------+ |                                                | +----------------------------+ |
                              +--------------------------------+                                                +--------------------------------+
```

Event Bus API:
--------------

All the calls between the components are documented here:

[interop tests API doc](http://doc.f-interop.eu/interop/)

You are really into knowing how this happens, look into the python module `ioppytest-utils`, which includes a package called `messages`.


Running a test suite:
---------------------

User needs :

- an implementation under test (IUT) of a standard supported/protocol by ioppytest framework - e.g. a `CoAP` client -
- to run [the agent component](http://doc.f-interop.eu/interop/#agent) into his/her environment.
  The `agent`  basically plays the role of a vpn-client , and which will route all the
  packets sent from the IUT (on a certain ipv6 network) to the
  backend -which is later on routed to second IUT (and viceversa)-.
- a user interface to help coordinating the tests (either GUI or CLI component)

`ioppytest` includes a Makefile which can be used as  `make <cmd>`, which simplifies the building of components needed
for running the interop test suites.
For more information execute `make help`

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

- user drives one IUT and wants to run tests against one of the
automated-IUTs the framework supports
- user drives both implementations (IUTs) taking part in the interop
session
- user1 drives an IUT, user2 drives an IUT, users are either both
in-situ, or remotely located.

# (opt 1) Running a test suite using F-Interop platform

go to [go.f-interop.eu](go.f-interop.eu) and follow the instructions

Recommended option (more user friendly).

# (opt 2) Running a test suite standalone

for this, you will use ioppytest_cli  as CLI for
interfacing with testing tool (comms go over AMQP event bus).

Recommended option only for testing tool contributors.

## (opt 2.1) Set up up the message broker

`ioppytest`, the interop testing tool, uses `RabbitMQ` (RMQ), a `AMQP` message broker. 
All components taking part of the test setup use AMQP for communications, this is used between 
remote components, like the `agent`, but also for interprocess communications of `ioppytest` tool.

If using [go.f-interop.eu](go.f-interop.eu) then this is automatically set-up for you.

When running a standalone setup the user first needs to have a RMQ broker running..

The options for this are:

- install locally RabbitMQ message broker on local machine,
create RMQ vhost, user, pass on local machine

    (# TODO add instructions)

- Request a remote vhost and credentials (user,pass) to me (see contact at the bottom of document).


don't hesitate to contact me, this is a very simple procedure and it's free :D

## (opt 2.2) Export AMQP environment variables

after having created a vhost with its user/password, export in the machine 
where the testing tool is running the following env vars:

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

## (opt 2.5) Running the testing tool (CoAP testing tool example)

This runs the docker containers needed for running the tests.
```
make run-coap-testing-tool
```

## (opt 2.6) Talking to the testing tool (CLI)

This runs the `ioppytest-cli` which enables you to get info from testing tool, but also to input information.
E.g. ask to the testing tool __get the current state of the test__, __get table of all executed tests and verdicts__, etc

```
make run-cli
```

## (opt 2.7) Connecting to the VPN (agent)

if user's IUT is a CoAP client:

```
make run-agent-coap-client
```

if user's IUT is a CoAP server:

```
make run-agent-coap-server
```

## (opt 2.8) Running the second IUT

We have two options for running the second IUT. 
Either we test against agains an IUT driven by a second user (user-to-user interop session,
or we test against an IUT which is automated (single-user session). Second IUT then is 
driven automatically by some python driver code (special integration required).

### (opt 2.8.1) User to user session.

The second IUT needs to connect to the same VHOST the same way first IUT
did. For this user 2 should just export the same environment
variables, launch agent, and CLI as user 1 did. 

See intructions from 2.2 to 2.7.

### (opt 2.8.2) Single user session ( testing against an automated-IUT).

 If the user wants to run interop tests against one of the automated-IUT supported by ioppytest:

```
make run-coap-server
```

or for a coap client automated implementation:

```
make run-coap-client
```

This two calls automated the "reference implementations" used by `ioppytest`. 
For further testing against other automated-IUT please contact  

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

    please contact me, see contact at bottom of doc.


- Docker build returns a "cannot fetch package" or a "cannot resolve .."

    try using ```--no-cache``` for the docker build

    more info http://stackoverflow.com/questions/24991136/docker-build-could-not-resolve-archive-ubuntu-com-apt-get-fails-to-install-a


Contact:
--------

federicosismondi<at>gmail<dot>com (recommended)
