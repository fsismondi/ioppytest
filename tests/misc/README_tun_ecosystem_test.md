# This describes what needs to be set up for TUN ecosystem tests

The ecosystem is as follows:

(agents, TUNs, automation code for sending pings on demand, packet router, CLI for demaning OS envs to send pings)

```
             +--------------------------------+                                                                        +--------------------------------+
             | +----------------------------+ |                                                                        | +----------------------------+ |
             | |         IPv6-based         | |                                                                        | |         IPv6-based         | |
             | |        communicating       | |                                                                        | |        communicating       | |
             | |      piece of software     | |                                                                        | |      piece of software     | |
             | |      (e.g. automated-IUT)  | |                     +----------------------------+                     | |      (e.g. automated-IUT)  | |
             | |                            | |                     |                            |                     | |                            | |
             | +----------------------------+ |                     |      Packet Routerased     |                     | +----------------------------+ |
      PC     |                                |                     |    (routes AMQP packets)   |                     |                                | PC
      user 1 | +------tun interface--------+  |                     |                            |                     | +------tun interface--------+  | user 2
             |                                |                     |                            |                     |                                |
             |            Agent (agent_x)     |                     +----------------------------+                     |            Agent (agent_y)     |
             |                                |                                                                        |                                |
             |          (tun mode)            |                              ^    +                                    |          (tun mode)            |
             |                                |                              |    |                                    |                                |
             |                                |                              |    |                                    |                                |
             +--------------------------------+                              |    |                                    +--------------------------------+
                                                         *.fromAgent.agent_x |    |  *.toAgent.agent_y
                           +     ^                                           |    |                                                 +     ^
                           |     |                                           |    |                                                 |     |
data.tun.fromAgent.agent_x |     | data.tun.toAgent.agent_x                  |    |                      data.tun.fromAgent.agent_y |     | data.tun.toAgent.agent_y
                           |     |                                           |    |                                                 |     |
                           v     +                                           +    v                                                 v     +

             +------------------------------------------------------------------------------------------------------------------------------------------------>
                                                                              AMQP Event Bus
             <-------------------------------------------------------------------------------------------------------------------------------------------------+

```

1. Build docker images:

build docker debian based image which launches agent + automated IUT:

`docker build . -t tun_ecosystem_test_agent_from_debian -f tests/misc/dockerfile_for_ecosystem_test__agent_from_debian_base`

build docker image for packet router:

`docker build . -t tun_ecosystem_test_packet_router -f tests/misc/dockerfile_for_ecosystem_test__packet_router`

2. Prepare components for test:

export an AMQP session url:

`export AMQP_URL=amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/jenkins.tun_ecosystem_test_agent_from_debian`

run packet router container:
`docker run  --rm -it --env AMQP_URL=$AMQP_URL --privileged --sysctl net.ipv6.conf.all.disable_ipv6=0  tun_ecosystem_test_packet_router`

run container with agent1 (tunnel endpoint 1)
`docker run -it --env AMQP_URL=$AMQP_URL --env NODE_NAME=agent1 --env AGENT_IPV6_PREFIX=bbbb --env AGENT_IPV6_HOST=1 --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged tun_ecosystem_test_agent_from_debian`

run container with agent2 (tunnel endpoint 2)
`docker run -it --env AMQP_URL=$AMQP_URL --env NODE_NAME=agent2 --env AGENT_IPV6_PREFIX=bbbb --env AGENT_IPV6_HOST=2 --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged tun_ecosystem_test_agent_from_debian`

3. Run tests:

install CLI:
`pip install ioppytest-utils`

run ping from agent1 to bbbb::2
`python3 -m ioppytest_cli _test_automated_iut_reaches_another_other_implementation --origin-node agent1 --target-host bbbb::2`

run ping from agent2 to bbbb::1
`python3 -m ioppytest_cli _test_automated_iut_reaches_another_other_implementation --origin-node agent2 --target-host bbbb::1`

