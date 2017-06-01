#!/usr/bin/env bash
echo """
docker images naming must follow the following conventions:

resource_type-sub_type-resource_name-version

resource_type, sub_type and resource_name cannot contain any special character, nor  '-'
version format must comply to vx.x

examples:

automated_iut-coap_client-coapthon-v0.1
automated_iut-coap_server-californium-v0.1
testing_tool-performance-coap-v0.1
testing_tool-interoperability-coap-v0.1
testing_tool-conformance-coap-v0.1
testing_tool-conformance-6tisch-v0.1
reference_iut-coap_client-coapthon-v0.1
reference_iut-coap_client (alias)
reference_iut-coap_server-californium-v0.1
reference_iut-coap_server (alias)
"""

# let's build the three 3 images used by F-Interop platform
docker build -t automated_iut-coap_server-californium-v0.1 -f automated_IUTs/coap_server_californium/Dockerfile .
docker build -t automated_iut-coap_client-coapthon-v0.1 -f automated_IUTs/coap_client_coapthon/Dockerfile .
docker build -t testing_tool-interoperability-coap-v-0.5 .

# the testing tool for interop and conformance is the same
docker tag testing_tool-interoperability-coap-v-0.5:latest testing_tool-conformance-coap-v-0.5

# reference iut for coap server is automated_iut-coap_server-californium-v0.1
docker tag automated_iut-coap_server-californium-v0.1:latest reference_iut-coap_server-californium-v0.1
# which can be run also by the name of reference_iut-coap_server
docker tag automated_iut-coap_server-californium-v0.1:latest reference_iut-coap_server

# reference iut for coap client:
docker tag automated_iut-coap_client-coapthon-v0.1:latest reference_iut-coap_client-coapthon-v0.1
# which can be run also by the name of reference_iut-coap_client
docker tag automated_iut-coap_client-coapthon-v0.1:latest reference_iut-coap_client


