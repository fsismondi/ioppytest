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

### Please install the agent using PyPi (python script):

\n\n

using virtual env (recommended): 

\n

    install virtualenv:

\n

        `pip install virtualenv`

\n

    create a python 2.7 evironment:

\n

        `virtualenv -p /usr/bin/python2.7 my_venv`

\n

    activate environment:

\n

        `source my_venv/bin/activate`

\n

    install package:

\n

        `pip install ioppytest-agent`

\n
\n

or else (without virtualenv):

\n
\n

        `python2.7 -m pip install ioppytest-agent`
 
\n
\n
 
You can execute directly from source code, for this use, and check out README.md:
 
\n
 
        `git clone --recursive https://gitlab.f-interop.eu/f-interop-contributors/agent`

\n\n
------------------------------------------------------------------------------

\n\n

Installation didn't work? Check the agent dependencies:
    - python 2.7 needed (virtualenv use recommended if no py2.7 version installed in OS )
    - for MacOs users, tuntap driver is needed: `brew install Caskroom/cask/tuntap`

\n\n

------------------------------------------------------------------------------

### Run (choose if either SomeAgentName1 or SomeAgentName2):

\n\n

    `sudo -E ioppytest-agent connect --url $AMQP_URL --exchange $AMQP_EXCHANGE  --name SomeAgentName1`

\n\n

or

\n\n

    `sudo -E ioppytest-agent connect --url $AMQP_URL --exchange $AMQP_EXCHANGE  --name SomeAgentName2`

------------------------------------------------------------------------------
```

"""

vpn_setup = """
### How does my implementation will reach other implementations?

\n\n

We need to set up a IP tunnel between both implementations under test (IUT). 
The agent component creates a tun interface in your PC which allows you to communicate with other implementations, the 
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
------------------------------------------------------------------------------
\n\n

```
fsismondi@carbonero250:~/dev/agent$ sudo -E ioppytest-agent connect --url $AMQP_URL --exchange $AMQP_EXCHANGE --name coap_client
Password: ********

  _                              _              _                                     _
 (_)  ___   _ __   _ __   _   _ | |_  ___  ___ | |_         __ _   __ _   ___  _ __  | |_
 | | / _ \\ | '_ \\ | '_ \\ | | | || __|/ _ \\/ __|| __|_____  / _` | / _` | / _ \\| '_ \\ | __|
 | || (_) || |_) || |_) || |_| || |_|  __/\\__ \\| |_|_____|| (_| || (_| ||  __/| | | || |_
 |_| \\___/ | .__/ | .__/  \\__, | \\__|\\___||___/ \\__|       \\__,_| \\__, | \\___||_| |_| \\__|
           |_|    |_|     |___/                                   |___/


INFO:agent.agent_cli:Try to connect with {'session': <session_id>, 'user': <user_id>, 'exchange': 'amq.topic', 'password': <pass>, 'server': 'mq.f-interop.eu:443', 'name': u'coap_client'}
INFO:kombu.mixins:Connected to amqp://<user_id>:**@mq.f-interop.eu:443/<session_id>
INFO:kombu.mixins:Connected to amqp://<user_id>:**@mq.f-interop.eu:443/<session_id>
INFO:agent.connectors.tun:Queue: consumer: coap_client.tun?rkey=toAgent.coap_client.ip.tun.start bound to: toAgent.coap_client.ip.tun.start
INFO:agent.connectors.tun:Queue: consumer: coap_client.tun?rkey=toAgent.coap_client.ip.tun.packet.raw bound to: toAgent.coap_client.ip.tun.packet.raw
INFO:agent.connectors.core:Agent READY, listening on the event bus for ctrl messages and data packets..
```

\n\n

------------------------------------------------------------------------------
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

(!) Note: this may not work under these circumstances:
    - this is a user to user session, and the other user hasn't yet started his agent component 
    - if some user is using agent in --serial-mode (network configs may be slightly different)   

\n\n
----------------------------------------------------------------------------
\n\n

Now you could try ping6 the other implementation in the VPN:

\n\n

`fsismondi@carbonero250:~$ ping6 bbbb::2`  should show:

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
