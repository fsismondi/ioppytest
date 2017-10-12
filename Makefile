# TODO add docker-build for building testing tool
# TODO add run for running testing tool locally (from docker image of supervisor?)

docker-build-all:
	@echo $(info_message)

	@echo "Starting to build all docker images.. "
	# let's build the automated/reference IUT images used by F-Interop platform
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

	# reference iut (only reference per sub_type in F-Interop plaform) e.g.: for coap server is californium
	docker tag automated_iut-coap_server-californium-v0.8:latest reference_iut-coap_server-californium-v0.8
	docker tag automated_iut-coap_client-coapthon-v0.8:latest reference_iut-coap_client-coapthon-v0.8

	# which can be run also by using "reference_iut-coap_client" or "reference_iut-coap_server"
	# TODO just use this name and not the one with the sub_type
	docker tag automated_iut-coap_client-coapthon-v0.8:latest reference_iut-coap_client
	docker tag automated_iut-coap_server-californium-v0.8:latest reference_iut-coap_server

run-coap-testing-tool:
	@echo "Using env vars:"
	@echo $(AMQP_URL)
	@echo $(AMQP_EXCHANGE)
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-coap testing_tool-interoperability-coap

run-coap-client:
	@echo "Using env vars:"
	@echo $(AMQP_URL)
	@echo $(AMQP_EXCHANGE)
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name reference_iut-coap_client reference_iut-coap_client

run-coap-server:
	@echo "Using env vars:"
	@echo $(AMQP_URL)
	@echo $(AMQP_EXCHANGE)
	docker run -d -t --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name reference_iut-coap_server reference_iut-coap_server

stop-coap-testing-tool:
	docker stop testing_tool-interoperability-coap

stop-coap-server:
	docker stop reference_iut-coap_server

stop-coap-client:
	docker stop reference_iut-coap_client

stop-all:
	# (exit 0) -> so the script continues on errors
	$(MAKE) stop-coap-testing-tool --keep-going ; exit 0
	$(MAKE) stop-coap-server --keep-going ; exit 0
	$(MAKE) stop-coap-client --keep-going ; exit 0

get-logs:
	@echo ">>>>> start logs testing_tool-interoperability-coap"
	docker logs testing_tool-interoperability-coap ; exit 0
	@echo "<<<<< end logs testing_tool-interoperability-coap \n"

	@echo ">>>>> start logs reference_iut-coap_server"
	docker logs reference_iut-coap_server ; exit 0
	@echo "<<<<< end logs reference_iut-coap_server \n"

	@echo ">>>>> start logs reference_iut-coap_client"
	docker logs reference_iut-coap_client ; exit 0
	@echo "<<<<< end logs reference_iut-coap_client \n"

install-requirements:
	@echo 'installing py2 dependencies'
	@python -m pip install -r coap_testing_tool/agent/requirements.txt --upgrade
	@echo 'installing py3 dependencies'
	@python3 -m pip install -r coap_testing_tool/test_coordinator/requirements.txt --upgrade
	@python3 -m pip install -r coap_testing_tool/test_analysis_tool/requirements.txt --upgrade
	@python3 -m pip install -r coap_testing_tool/packet_router/requirements.txt --upgrade
	@python3 -m pip install -r coap_testing_tool/sniffer/requirements.txt --upgrade
	@python3 -m pip install -r coap_testing_tool/webserver/requirements.txt --upgrade


info_message = """ \
	docker images naming must follow the following conventions: \n\
	\n\
	resource_type-sub_type-resource_name-version \n\
	\n\
	resource_type, sub_type and resource_name cannot contain any special character, nor  '-' \n\
	version format must comply to vx.x \n\
	\n\
	examples: \n\
	\n\
	automated_iut-coap_client-coapthon-v0.8 \n\
	automated_iut-coap_server-californium-v0.8 \n\
	\n\
	testing_tool-performance-coap-v0.8 \n\
	testing_tool-interoperability-coap-v0.8 \n\
	testing_tool-interoperability-coap (alias to last version) \n\
	testing_tool-conformance-coap-v0.8 \n\
	testing_tool-conformance-coap (alias to last version) \n\
	testing_tool-conformance-6tisch-v0.8 \n\
	\n\
	reference_iut-coap_client-coapthon-v0.8 \n\
	reference_iut-coap_client (alias to last version) \n\
	reference_iut-coap_server-californium-v0.8 \n\
	reference_iut-coap_server (alias to last version) \n\
	"""