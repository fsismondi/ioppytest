#!/usr/bin/env bash
echo """
docker images naming must follow the following conventions:

resource_type-sub_type-resource_name-version

resource_type, sub_type and resource_name cannot contain any special character, nor  '-'
version format must comply to vx.x

examples:

automated_iut-coap_client-coapthon-v0.8
automated_iut-coap_server-californium-v0.8

testing_tool-performance-coap-v0.8
testing_tool-interoperability-coap-v0.8
testing_tool-interoperability-coap (alias to last version)
testing_tool-conformance-coap-v0.8
testing_tool-conformance-coap (alias to last version)
testing_tool-conformance-6tisch-v0.8
"""

# let's build the automated IUT images used by F-Interop platform
docker build -t automated_iut-coap_server-californium-v0.8 -f automated_IUTs/coap_server_californium/Dockerfile .
docker build -t automated_iut-coap_client-californium-v0.8 -f automated_IUTs/coap_client_californium/Dockerfile .
docker build -t automated_iut-coap_server-coapthon-v0.8 -f automated_IUTs/coap_server_coapthon/Dockerfile .
docker build -t automated_iut-coap_client-coapthon-v0.8 -f automated_IUTs/coap_client_coapthon/Dockerfile .

# let's build the testing tool image (same for interop and conformance)
docker build -t testing_tool-interoperability-coap-v0.8 .

# the testing tool for interop and conformance are the same, so lets tag it as such
docker tag testing_tool-interoperability-coap-v0.8:latest testing_tool-conformance-coap-v0.8

# tag all last version images also with a version-less name
docker tag testing_tool-interoperability-coap-v0.8:latest testing_tool-interoperability-coap
docker tag testing_tool-conformance-coap-v0.8:latest testing_tool-conformance-coap

docker tag automated_iut-coap_client-coapthon-v0.8:latest automated_iut-coap_client-coapthon
docker tag automated_iut-coap_server-coapthon-v0.8:latest automated_iut-coap_server-coapthon

docker tag automated_iut-coap_client-californium-v0.8:latest automated_iut-coap_client-californium
docker tag automated_iut-coap_server-californium-v0.8:latest automated_iut-coap_server-californium

# for conformance testing we use "reference implementations"
docker tag automated_iut-coap_client-coapthon-v0.8:latest reference_iut-coap_client
docker tag automated_iut-coap_server-californium-v0.8:latest reference_iut-coap_server
