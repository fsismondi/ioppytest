# Packet Router

Component for routing packets between IUTs.

## About the component

- The routing happens on the AMQP level, not IP one (this way we can test even L3 & L2 protocols)
- The routing table (built based on AMQP routing keys) is built dynamically from the test configuration yaml document

## Installation

TODO

## Execution

```
python3 -m ioppytest.packet_router
```

## TODO

- need to be able to drop packets on demand for test cases where message drops are considered (i.e. CoAP_CFG_LOSSY config)