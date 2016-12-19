CoAP Testing Tool:
------------------

This repo conaints all necessary software (and their dependencies) for running a 
CoAP interoperability test session.

This can be run as standalone software and also integrated to f-interop 
architecture.

### TODO
- add client automated IUT
- add feat for handling step by step analysis
- add more functional testing of coordinator component
- add windows support(?)
- document isntallation of requirements and dependencies

### CoAP Testing tools components

The CoAP testing tool handles the coordination, sniffing, dissection and analysis of CoAP test suite.
It's based on the test scenarios and test cases described in 
[ETSI CoAP test description](http://www.etsi.org/plugtests/CoAP/Document/CoAP_TestDescriptions_v015.pdf)

For description of components please visit: [f-interop doc](doc.f-interop.eu)


### Running it as standalone software

for debian based OS & macos:


- installation 

  - install RMQ broker
  - install dependencies
  - install supervisor (for spawning and monitoring processes)


- create credentials for connection, vhost, and then export connection parameters for the AMQP connection:

    e.g.: 
    ```
    export AMQP_VHOST=‘/‘
    export AMQP_EXCHANGE=‘default'
    export AMQP_USER=‘walrus’
    export AMQP_PASS=‘somePassword’
    export AMQP_SERVER=‘f-interop.rennes.inria.fr'
    ```

- run CoAP testing tool and monitor processes
    ```
    cd coap_testing_tool
    sudo supervisord -c supervisor.conf 
    sudo supervisorctl -c supervisor.conf  

    ```



