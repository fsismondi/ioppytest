# Packet Router

Component for routing packets between IUTs.

## About the component

- The routing happens on the AMQP level, not IP one (for being protocol agnostic).
- The information on the routing keys (info about which agent sent the message), 
plus the information on the test topology should be enough input for the packet router 

## Installation

## Execution

## TODO
- need to be able to build the routing table dynamically with the test config
- need to be able to drop packets on demand for test cases where message drops are considered (i.e. CoAP_CFG_LOSSY config)