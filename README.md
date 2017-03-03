CoAP Testing Tool:
------------------

This repo conaints all necessary software (and their dependencies) for running a 
CoAP interoperability test session.

This can be run as standalone software and also integrated to f-interop 
architecture.

### TODO
- add coap client automated IUT
- add feat for handling step by step analysis
- add more unit testing of coordinator component
- document isntallation of requirements and dependencies

### CoAP Testing tools components

The CoAP testing tool handles the coordination, sniffing, dissection and analysis of CoAP test suite.
It's based on the test scenarios and test cases described in 
[ETSI CoAP test description](http://www.etsi.org/plugtests/CoAP/Document/CoAP_TestDescriptions_v015.pdf)

For description of components please visit: [f-interop doc](doc.f-interop.eu)

### Clonning the project
```
git clone --recursive git@gitlab.distantaccess.com:fsismondi/coap_testing_tool.git
cd coap_testing_tool
git submodule update --init --recursive
```

### Running it as standalone software

for debian based OS & macos:


- installation 

  - install locally RMQ broker on local machine
    - create RMQ vhost, user, pass on local machine
    
    note: on a non-standalone deployment the RMQ broker is provided by f-interop
    
  - install supervisor (for spawning and monitoring processes)
  
- install testing tool requirements:
	change in anible/main.yml the variable unix_user from f-interop to your
	local unix user, then run ansible script:
    
    ```
    cd coap_testing_tool
    ansible-playbook -i ansible/hosts.local ansible/main.yml --ask-become-pass
    ```

- export credentials, server, and vhost for local RMQ connection: 
    
    ```
    export AMQP_URL='amqp://someUser:somePassword@server/amqp_vhost'
    export AMQP_EXCHANGE='default'
    ```

- run CoAP testing tool and monitor processes
    
    ```
    cd coap_testing_tool
    sudo -E supervisord -c supervisor.conf 
    sudo supervisorctl -c supervisor.conf  

    ```
	note: use -E when launching supervisor process, it preserves the env vars



