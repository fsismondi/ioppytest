from ioppytest import AMQP_URL, AMQP_EXCHANGE

env_vars_export = """

### Agent requirements

The agent component, which is needed for running interop tests works for both MacOs (tested with MacOs 10.12.x)
and also debian-based distributions.

(!) Windows is for the time being not supported by the agent. If your implementation can run into a virtual machine
or docker container please setup that environment so yo can run the agent from within.

------------------------------------------------------------------------------

### Prepare environment

Please open a Terminal where to execute the agent component 
and export environment variables: 

`export AMQP_URL="{url}"`

------------------------------------------------------------------------------
""".format(url=AMQP_URL)


agent_install_help = """

### Please install the agent using PyPi (python script):

\n\n

using virtual env (recommended):

\n

\n
```

# install venv
> pip install virtualenv 

# create a python 2.7 env
> virtualenv -p /usr/bin/python2.7 my_venv 

# activate env
> source my_venv/bin/activate

# install package
> pip install ioppytest-agent 

```
\n\n

or else (without virtualenv):

```

> python2.7 -m pip install ioppytest-agent

```
\n\n

------------------------------------------------------------------------------

\n\n

You can execute directly from source code, for this use, and check out README.md:

\n

```

> git clone --recursive https://gitlab.f-interop.eu/f-interop-contributors/agent

```

\n\n
------------------------------------------------------------------------------

\n\n

Installation didn't work? Check the agent dependencies:

\n
    - python 2.7 needed (virtualenv use recommended if no py2.7 version installed in OS )
    - for MacOs users, tuntap driver is needed: `brew install Caskroom/cask/tuntap`

\n\n
"""

help_agents_run_for_raw_ip_mode = """

------------------------------------------------------------------------------

### Run (use AgentNameHost1 or AgentNameHost2 depending on the role of your implementation):

\n\n

`sudo -E python2.7 -m agent connect --url $AMQP_URL --name AgentNameHost1 --force-bootstrap --ipv6-host 1 --ipv6-prefix bbbb`

\n\n

or

\n\n

`sudo -E python2.7 -m agent connect --url $AMQP_URL --name AgentNameHost2 --force-bootstrap --ipv6-host 2 --ipv6-prefix bbbb`

\n\n
\n\n

If your implementation doesnt run as software hosted directly in the OS (e.g. the implementation is an IoT device in a 
WSN network) please check out the agent help section describing these setups 

\n\n

`python2.7 -m agent --help` 

------------------------------------------------------------------------------
```

"""

vpn_setup = """
### How does my implementation will reach other implementations?

\n
\n

For running the tests both implementations need to be reachable, for this
we will set up a IP tunnel (ipv6 only) between both implementations under test (IUT). 
The software component for setting this up is called the agent, it plays a role similar to a VPN client.

\n

The following doc will describe how to install and launch the agent. This component will create a tun interface in your 
PC which allows you to communicate with other implementations, the solution goes more or less like this:

\n
\n

```
       +--------------------------------+                                             +--------------------------------+
       | +----------------------------+ |                                             | +----------------------------+ |
       | |         IPv6-based         | |                                             | |         IPv6-based         | |
       | |        communicating       | |                                             | |        communicating       | |
       | |      piece of software     | |                                             | |      piece of software     | |
       | |      (e.g. coap client)    | |   +----------------------------+            | |      (e.g. coap sever)     | |
       | |                            | |   |                            |            | |                            | |
       | +----------------------------+ |   |                            |            | +----------------------------+ |
PC     |                                |   |       Packet Router        |      PC    |                                |
user 1 | +------tun interface---------+ |   |                            |      user2 | +------tun interface---------+ |
       |                                |   |                            |            |                                |
       |            Agent               |   +----------------------------+            |            Agent               |
       |                                |                                             |                                |
       |          (tun mode)            |               ^    +                        |          (tun mode)            |
       |                                |               |    |                        |                                |
       |                                |               |    |                        |                                |
       +--------------------------------+               |    |                        +--------------------------------+
                                                r_key_1 |    |  r_key_4
                     +     ^                       &    |    |     &                                ^     +
                     |     |                    r_key_3 |    |  r_key_2                             |     |
             r_key_1 |     | r_key_2                    |    |                              r_key_4 |     | r_key_3
                     |     |                            |    |                                      |     |
                     v     +                            +    v                                      +     v

     +----------------------------------------------------------------------------------------------------------------->
                                                AMQP Event Bus
     <-----------------------------------------------------------------------------------------------------------------+
```

\n\n\n\n

r_key_1=fromAgent.agent_1_name.ip.tun.packet.raw
r_key_2=toAgent.agent_1_name.ip.tun.packet.raw
r_key_3=fromAgent.agent_2_name.ip.tun.packet.raw
r_key_4=toAgent.agent_2_name.ip.tun.packet.raw

------------------------------------------------------------------------------

### More about the agent component:

\n\n

    [link to agent README](https://gitlab.f-interop.eu/f-interop-contributors/agent/blob/master/README.md)

\n\n
"""

vpn_ping_tests = """

----------------------------------------------------------------------------
----------------------------------------------------------------------------
## How do I know if the agent is working?

If everything goes well you should see in your terminal sth like this:

\n\n

```
------------------------------------------------------------------------------

➜  /tmp sudo -E python -m agent connect --url $AMQP_URL --name coap_server --force-bootstrap --ipv6-host 2 --ipv6-prefix bbbb
Password:

  _                              _              _                                     _
 (_)  ___   _ __   _ __   _   _ | |_  ___  ___ | |_         __ _   __ _   ___  _ __  | |_
 | | / _ \ | '_ \ | '_ \ | | | || __|/ _ \/ __|| __|_____  / _` | / _` | / _ \| '_ \ | __|
 | || (_) || |_) || |_) || |_| || |_|  __/\__ \| |_|_____|| (_| || (_| ||  __/| | | || |_
 |_| \___/ | .__/ | .__/  \__, | \__|\___||___/ \__|       \__,_| \__, | \___||_| |_| \__|
           |_|    |_|     |___/                                   |___/


INFO:agent.agent_cli:Try to connect with {'session': u'session05', 'user': u'paul', 'exchange': u'amq.topic', 'password': <XXXXXXXXX>, 'server': u'f-interop.rennes.inria.fr', 'name': u'coap_server'}
INFO:agent.connectors.base:starting tun interface
INFO:agent.connectors.base:Starting open tun [darwin]
DEBUG:agent.utils.opentun:IP info:
 {'ipv4_network': [10, 2, 0, 0], 'ipv4_netmask': [255, 255, 0, 0], 'ipv6_no_forwarding': True, 're_route_packets_if': None, 'ipv6_prefix': u'bbbb', 're_route_packets_prefix': None, 'ipv4_host': '2.2.2.2', 'ipv6_host': u'2', 're_route_packets_host': None}
INFO:agent.utils.opentun:opening tun interface
INFO:agent.utils.opentun:configuring IPv6 address...
INFO:agent.utils.opentun:
created following virtual interface:
------------------------------------------------------------------------
tun0: flags=8851<UP,POINTOPOINT,RUNNING,SIMPLEX,MULTICAST> mtu 1500
    inet6 fe80::aebc:32ff:fecd:f38b%tun0 prefixlen 64 scopeid 0xc
    inet6 bbbb::2 prefixlen 64 tentative
    inet6 fe80::2%tun0 prefixlen 64 optimistic scopeid 0xc
    nd6 options=201<PERFORMNUD,DAD>
    open (pid 3749)
------------------------------------------------------------------------
INFO:agent.utils.opentun:
update routing table:
default via 2001:660:7303:250::1 dev en3
default via fe80::%utun0 dev utun0
2001:660:7303:250::/64 dev en3  scope link
bbbb::/64 via fe80::aebc:32ff:fecd:f38b%tun0 dev tun0
fe80::/64 via fe80::aebc:32ff:fecd:f38b%tun0 dev tun0
fe80::/64 via fe80::1%lo0 dev lo0
fe80::/64 dev awdl0  scope link
fe80::/64 dev en3  scope link
fe80::/64 via fe80::3b34:cd72:b27c:9c5f%utun0 dev utun0
fe80::/64 via fe80::aebc:32ff:fecd:f38b%tun0 dev tun0
ff01::/32 via ::1 dev lo0
ff01::/32 dev awdl0  scope link
ff01::/32 dev en3  scope link
ff01::/32 via fe80::3b34:cd72:b27c:9c5f%utun0 dev utun0
ff01::/32 via fe80::aebc:32ff:fecd:f38b%tun0 dev tun0
ff02::/32 via ::1 dev lo0
ff02::/32 dev awdl0  scope link
ff02::/32 dev en3  scope link
ff02::/32 via fe80::3b34:cd72:b27c:9c5f%utun0 dev utun0
ff02::/32 via fe80::aebc:32ff:fecd:f38b%tun0 dev tun0
------------------------------------------------------------------------
DEBUG:agent.utils.opentun:packet captured on tun interface: (64B) 60-00-00-00-00-18-3a-ff-00-00-00-00-00-00-00-00-00-00-00-00-00-00-00-00-ff-02-00-00-00-00-00-00-00-00-00-01-ff-00-00-02-87-00-7c-23-00-00-00-00-fe-80-00-00-00-00-00-00-00-00-00-00-00-00-00-02
DEBUG:agent.utils.opentun:Pushing message to topic: fromAgent.coap_server.ip.tun.packet.raw
INFO:agent.utils.opentun:Messaged captured in tun. Pushing message to testing tool. Message count (uplink): 1

      _
     / \\
    /   \\
   /     \\
  /       \\
 /__     __\\
    |   |              _ _       _
    |   |             | (_)     | |
    |   |  _   _ _ __ | |_ _ __ | | __
    |   | | | | | '_ \\| | | '_ \\| |/ /
    |   | | |_| | |_) | | | | | |   <
    |   |  \\__,_| .__/|_|_|_| |_|_|\\_\\
    |   |       | |
    |   |       |_|
    !___!
   \\  O  /
    \\/|\\/
      |
     / \\
   _/   \\ _

INFO:root:Publishing MsgAgentTunStarted(_api_version = 1.0.15, ipv4_host = 2.2.2.2, ipv4_netmask = [255, 255, 0, 0], ipv4_network = [10, 2, 0, 0], ipv6_host = 2, ipv6_no_forwarding = True, ipv6_prefix = bbbb, name = coap_server, re_route_packets_host = None, re_route_packets_if = None, re_route_packets_prefix = None, )

INFO:agent.utils.opentun:
 # # # # # # # # # # # # OPEN TUN # # # # # # # # # # # #
 data packet TUN interface -> EventBus
{"_api_version": "1.0.15", "data": [96, 0, 0, 0, 0, 24, 58, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 255, 0, 0, 2, 135, 0, 124, 35, 0, 0, 0, 0, 254, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2], "interface_name": "tun0", "timestamp": 1531387551}
 # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


------------------------------------------------------------------------------

```
\n\n

## How can I test that is actually working?

(now the agent should be boostrapped, and the network interfaces ready to go..)

\n\n

------------------------------------------------------------------------------

\n\n

### Test1 : check the tun interface was created 

\n\n
------------------------------------------------------------------------------

\n\n

`fsismondi@carbonero250:~$ ifconfig`  this should show:

\n\n

```
    tun0: flags=8851<UP,POINTOPOINT,RUNNING,SIMPLEX,MULTICAST> mtu 1500
        inet6 fe80::aebc:32ff:fecd:f38b%tun0 prefixlen 64 scopeid 0xc 
        inet6 bbbb::1 prefixlen 64 
        inet6 fe80::1%tun0 prefixlen 64 scopeid 0xc 
        nd6 options=201<PERFORMNUD,DAD>
        open (pid 7627)
```

----------------------------------------------------------------------------
----------------------------------------------------------------------------

### Test2 : ping the other device 

\n\n
----------------------------------------------------------------------------

\n\n

Now you could try ping6 the other implementation in the VPN:

\n\n

(the destination IPv6 is either bbbb::1 or bbbb::2)

`fsismondi@carbonero250:~$ ping6 bbbb::2` 

\n\n

```
    fsismondi@carbonero250:~$ ping6 bbbb::2
    PING6(56=40+8+8 bytes) bbbb::1 --> bbbb::2
    16 bytes from bbbb::2, icmp_seq=0 hlim=64 time=65.824 ms
    16 bytes from bbbb::2, icmp_seq=1 hlim=64 time=69.990 ms
    16 bytes from bbbb::2, icmp_seq=2 hlim=64 time=63.770 ms
    ^C
    --- bbbb::2 ping6 statistics ---
    3 packets transmitted, 3 packets received, 0.0% packet loss
    round-trip min/avg/max/std-dev = 63.770/66.528/69.990/2.588 ms
```

\n\n

(!) Note: this may not work under these circumstances:
    - this is a user to user session, and the other user hasn't yet started his agent component 
    - if some user is using agent in --serial-mode (network configs may be slightly different)   

\n\n
----------------------------------------------------------------------------

----------------------------------------------------------------------------

\n\n

while in the terminal where the agent runs you should see upstream and downstream packets log messages:

\n\n

```
INFO:agent.connectors.tun:Message received from testing tool. Injecting in Tun. Message count (downlink): 1

      _
     / \\
    /   \\
   /     \\
  /       \\
 /__     __\\
    |   |              _ _       _
    |   |             | (_)     | |
    |   |  _   _ _ __ | |_ _ __ | | __
    |   | | | | | '_ \\| | | '_ \\| |/ /
    |   | | |_| | |_) | | | | | |   <
    |   |  \\__,_| .__/|_|_|_| |_|_|\\_\\
    |   |       | |
    |   |       |_|
    !___!
   \\  O  /
    \\/|\\/
      |
     / \\
   _/   \\ _


INFO:agent.utils.opentun:
 # # # # # # # # # # # # OPEN TUN # # # # # # # # # # # #
 data packet TUN interface -> EventBus
{"_api_version": "1.0.15", "data": [96, 15, 46, 51, 0, 16, 58, 64, 187, 187, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 187, 187, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 128, 0, 58, 189, 105, 26, 0, 1, 90, 214, 243, 65, 0, 5, 22, 69], "interface_name": "tun0", "timestamp": 1524036417}
 # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
```

\n\n
----------------------------------------------------------------------------
\n\n

```
INFO:agent.connectors.tun:Message received from testing tool. Injecting in Tun. Message count (downlink): 1

    ___
   |   |
   |   |       _                     _ _       _
   |   |      | |                   | (_)     | |
   |   |    __| | _____      ___ __ | |_ _ __ | | __
   |   |   / _` |/ _ \\ \\ /\\ / / '_ \\| | | '_ '\\| |/ /
   |   |  | (_| | (_) \\ V  V /| | | | | | | | |   <
   |   |   \\__,_|\\___/ \\_/\\_/ |_| |_|_|_|_| |_|_|\\_\\
   |   |
 __!   !__,
 \\       / \\O
  \\     / \\/|
   \\   /    |
    \\ /    / \\
     Y   _/  _\\

INFO:agent.connectors.tun:
 # # # # # # # # # # # # OPEN TUN # # # # # # # # # # # #
 data packet EventBus -> TUN interface
{"_api_version": "1.0.15", "data": [96, 14, 68, 209, 0, 16, 58, 64, 187, 187, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 187, 187, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 129, 0, 57, 189, 105, 26, 0, 1, 90, 214, 243, 65, 0, 5, 22, 69], "interface_name": "tun0", "timestamp": 1524036417}
 # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
```
\n\n
----------------------------------------------------------------------------
\n\n


"""
