from ioppytest import AMQP_URL, AMQP_EXCHANGE

env_vars_export = """

### Prepare environment
Please open a Terminal where to execute the agent component (VPN client)
and export environment variables: 

------------------------------------------------------------------------------

`export AMQP_URL="%s"`

------------------------------------------------------------------------------

`export AMQP_EXCHANGE=%s`

------------------------------------------------------------------------------
""" % (AMQP_URL, AMQP_EXCHANGE)

agents_IP_tunnel_config = """

### Please download the agent component (python script):

\n\n

`git clone --recursive https://gitlab.f-interop.eu/f-interop-contributors/agent`

------------------------------------------------------------------------------

### Install dependencies:

`pip install -r requirements.txt`

\n\n

------------------------------------------------------------------------------

\n\n

Coming soon:

\n\n

PyPI (The Python Package Index ) agent python package distribution and installation process.

\n\n

------------------------------------------------------------------------------

### Run (choose if either SomeAgentName1 or SomeAgentName2):

(from inside agent repo)

\n\n

`sudo -E python -m agent connect --url $AMQP_URL --exchange $AMQP_EXCHANGE  --name SomeAgentName1`

\n\n

or

\n\n

`sudo -E python -m agent connect --url $AMQP_URL --exchange $AMQP_EXCHANGE  --name SomeAgentName2`

------------------------------------------------------------------------------
```

"""

vpn_setup = """
### What is this for?

\n\n

The agent creates a tun interface in your PC which allows you to comminicate with other implementations, the 
solution goes more or less like this:

\n\n

```
       +--------------------------------+                                             +--------------------------------+
       | +----------------------------+ |                                             | +----------------------------+ |
       | |         IPv6-based         | |                                             | |         IPv6-based         | |
       | |        communicating       | |                                             | |        communicating       | |
       | |      piece of software     | |                                             | |      piece of software     | |
       | |      (e.g. coap client)    | |   +----------------------------+            | |      (e.g. coap sever)     | |
       | |                            | |   |                            |            | |                            | |
       | +----------------------------+ |   |      Packet Router         |            | +----------------------------+ |
PC     |                                |   |    (routes AMQP packets)   |      PC    |                                |
user 1 | +------tun interface---------+ |   |                            |      user2 | +------tun interface---------+ |
       |                                |   |                            |            |                                |
       |            Agent               |   +----------------------------+            |            Agent               |
       |                                |                                             |                                |
       |          (tun mode)            |               ^    +                        |          (tun mode)            |
       |                                |               |    |                        |                                |
       |                                |               |    |                        |                                |
       +--------------------------------+               |    |                        +--------------------------------+
                                                r_key_1 |    |  r_key_2
                     +     ^                            |    |                                      +     ^
                     |     |                            |    |                                      |     |
             r_key_1 |     | r_key_2                    |    |                              r_key_3 |     | r_key_4
                     |     |                            |    |                                      |     |
                     v     +                            +    v                                      v     +

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
## How do I know if the agent is working?

If everything goes well you should see in your terminal sth like this:

\n\n
------------------------------------------------------------------------------
\n\n

```
fsismondi@carbonero250:~/dev/agent$ sudo -E python -m agent connect --url $AMQP_URL --exchange $AMQP_EXCHANGE --name coap_client
Password: ********

  _                              _              _                                     _
 (_)  ___   _ __   _ __   _   _ | |_  ___  ___ | |_         __ _   __ _   ___  _ __  | |_
 | | / _ \\ | '_ \\ | '_ \\ | | | || __|/ _ \\/ __|| __|_____  / _` | / _` | / _ \\| '_ \\ | __|
 | || (_) || |_) || |_) || |_| || |_|  __/\\__ \\| |_|_____|| (_| || (_| ||  __/| | | || |_
 |_| \\___/ | .__/ | .__/  \\__, | \\__|\\___||___/ \\__|       \\__,_| \\__, | \\___||_| |_| \\__|
           |_|    |_|     |___/                                   |___/


INFO:agent.agent_cli:Try to connect with {'session': u'1aa87ae1-27ec-40fe-b1f6-181761e77478', 'user': u'EKV0BXBX', 'exchange': u'amq.topic', 'password': u'RAOMI8S7', 'server': 'mq.dev.f-interop.eu:443', 'name': u'coap_client'}
INFO:kombu.mixins:Connected to amqp://EKV0BXBX:**@mq.dev.f-interop.eu:443/1aa87ae1-27ec-40fe-b1f6-181761e77478
INFO:kombu.mixins:Connected to amqp://EKV0BXBX:**@mq.dev.f-interop.eu:443/1aa87ae1-27ec-40fe-b1f6-181761e77478
INFO:agent.connectors.tun:Queue: consumer: coap_client.tun?rkey=toAgent.coap_client.ip.tun.start bound to: toAgent.coap_client.ip.tun.start
INFO:agent.connectors.tun:Queue: consumer: coap_client.tun?rkey=toAgent.coap_client.ip.tun.packet.raw bound to: toAgent.coap_client.ip.tun.packet.raw
INFO:agent.connectors.core:Agent READY, listening on the event bus for ctrl messages and data packets..
```

\n\n

------------------------------------------------------------------------------
## How do I know if the agent is working? (continuation..)

(now the agent should be boostrapped, and the network interfaces ready to go..)

\n\n

------------------------------------------------------------------------------

\n\n

### Test1 : check the tun interface was created 

\n\n

`fsismondi@carbonero250:~$ ifconfig`

\n\n

this should show:

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

### Test2 : ping the other device 
\n\n
(!) Note: this may not work under these circumstances:
- this is a user to user session, and the other user hasn't yet started his agent component 
- if somebody is using agent in --serial-mode (network configs may be slightly different)   
\n\n

Now you could try ping6 the other implementation in the VPN:

\n\n

`fsismondi@carbonero250:~$ ping6 bbbb::2`

\n\n

should show:

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
