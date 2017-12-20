from ioppytest import AMQP_URL, AMQP_EXCHANGE


env_vars_export = """
Export environment variables: 

`export AMQP_URL=%s`

`export AMQP_EXCHANGE=%s`
""" % (AMQP_URL, AMQP_EXCHANGE)

agents_IP_tunnel_config = """

### Please download the agent component (python script):

`git clone --recursive https://gitlab.f-interop.eu/f-interop-contributors/agent`

------------------------------------------------------------------------------

### Install dependencies:

`pip install -r requirements.txt`

------------------------------------------------------------------------------
### Run (choose if either SomeAgentName1 or SomeAgentName2):

`sudo -E python agent.py connect --url $AMQP_URL --exchange $AMQP_EXCHANGE  --name SomeAgentName1`

or

`sudo -E python agent.py connect --url $AMQP_URL --exchange $AMQP_EXCHANGE  --name SomeAgentName2`

------------------------------------------------------------------------------

### What is this for?

The agent creates a tun interface in your PC which allows you to comminicate with other implementations, the 
solution goes more or less like this:
```
                          +----------------+
                          |                |
                          |   AMQP broker  |
                          |                |
                          +----------------+
                                ^     +
                                |     |
data.tun.fromAgent.agent_name   |     |  data.tun.toAgent.agent_name
                                |     |
                                +     v
                 +---------------------------------+
                 |                                 |
                 |             Agent               |
                 |           (tun mode)            |
                 |                                 |
                 |   +------tun interface--------+ |
                 |  +----------------------------+ |
                 |  |         IPv6-based         | |
                 |  |        communicating       | |
                 |  |      piece of software     | |
                 |  |      (e.g. coap client)    | |
                 |  +----------------------------+ |
                 +---------------------------------+
```

------------------------------------------------------------------------------

### How do I know it's working?

If everything goes well you should see in your terminal sth like this:

fsismondi@carbonero250:~/dev/agent$ sudo -E python agent.py connect --url $AMQP_URL --exchange $AMQP_EXCHANGE --name coap_client
Password:

      ______    _____       _                       
     |  ____|  |_   _|     | |                      
     | |__ ______| |  _ __ | |_ ___ _ __ ___  _ __  
     |  __|______| | | '_ \| __/ _ \ '__/ _ \| '_ \ 
     | |        _| |_| | | | ||  __/ | | (_) | |_) |
     |_|       |_____|_| |_|\__\___|_|  \___/| .__/ 
                                             | |    
                                             |_|    

INFO:__main__:Try to connect with {'session': u'session05', 'user': u'paul', (...)
INFO:kombu.mixins:Connected to amqp://paul:**@f-interop.rennes.inria.fr:5672/session05
INFO:connectors.tun:tun listening to control plane 
INFO:connectors.tun:Queue: control.tun@coap_client 
INFO:connectors.tun:Topic: control.tun.toAgent.coap_client
INFO:connectors.tun:tun listening to data plane
INFO:connectors.tun:Queue: data.tun@coap_client
INFO:connectors.tun:Topic: data.tun.toAgent.coap_client
INFO:kombu.mixins:Connected to amqp://paul:**@f-interop.rennes.inria.fr:5672/session05
INFO:connectors.core:Backend ready to consume data

------------------------------------------------------------------------------
------------------------------------------------------------------------------
## After clicking in "Test Suite Start" you should be able to test the agent:

### Test1 : check the tun interface was created (unless agent was runned in --serial mode) 
\n\n
Then after the user triggers **test suite start** should see a new network interface in your PC:
\n\n
`fsismondi@carbonero250:~$ ifconfig`
\n\n
should show:
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

### Test2 : ping the other device (unless agent was runned in --serial mode) 
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

----------------------------------------------------------------------------

### More about the agent component:

[link to agent README](https://gitlab.f-interop.eu/f-interop-contributors/agent/blob/master/README.md)

\n\n
"""