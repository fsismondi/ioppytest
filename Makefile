version = 1.0

info:
	@echo $(info_message)

version:
	@echo ioppytest v$(version)

docker-build-all:
	@echo $(info_message)
	@echo "Starting to build docker images.. "
	$(MAKE) _docker-build-coap
	$(MAKE) _docker-build-coap-additional-resources
	$(MAKE) _docker-build-6lowpan
	$(MAKE) _docker-build-onem2m

run-cli:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@python3 -m ioppytest.utils.interop_cli repl

run-6lowpan-testing-tool:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-6lowpan testing_tool-interoperability-6lowpan

run-coap-testing-tool:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-coap testing_tool-interoperability-coap

run-onem2m-testing-tool:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-onem2m testing_tool-interoperability-onem2m

run-agent-coap-client:
	$(MAKE) _check-sudo
	cd ioppytest/agent && python agent.py connect --url $(AMQP_URL) --exchange $(AMQP_EXCHANGE)  --name coap_client_agent

run-agent-coap-server:
	$(MAKE) _check-sudo
	cd ioppytest/agent && python agent.py connect --url $(AMQP_URL) --exchange $(AMQP_EXCHANGE)  --name coap_client_server

run-coap-client:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name reference_iut-coap_client reference_iut-coap_client

run-coap-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d -t --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name reference_iut-coap_server reference_iut-coap_server

stop-onem2m-testing-tool:
	docker stop testing_tool-interoperability-onem2m

stop-6lowpan-testing-tool:
	docker stop testing_tool-interoperability-6lowpan

stop-coap-testing-tool:
	docker stop testing_tool-interoperability-coap

stop-coap-server:
	docker stop reference_iut-coap_server

stop-coap-client:
	docker stop reference_iut-coap_client

stop-all:
	# (exit 0) -> so the script continues on errors
	$(MAKE) stop-coap-testing-tool --keep-going ; exit 0
	$(MAKE) stop-6lowpan-testing-tool --keep-going ; exit 0
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

install-python-dependencies:
	@echo 'installing py2 dependencies...'
	@python -m pip -qq install -r ioppytest/agent/requirements.txt
	@echo 'installing py3 dependencies...'
	@python3 -m pip -qq install pytest
	@python3 -m pip -qq install -r ioppytest/test_coordinator/requirements.txt
	@python3 -m pip -qq install -r ioppytest/test_analysis_tool/requirements.txt
	@python3 -m pip -qq install -r ioppytest/packet_router/requirements.txt
	@python3 -m pip -qq install -r ioppytest/sniffer/requirements.txt
	@python3 -m pip -qq install -r ioppytest/webserver/requirements.txt
	@python3 -m pip -qq install -r ioppytest/utils/requirements.txt


_check-sudo:
	@runner=`whoami` ;\
	if test $$runner != "root" ;\
	then \
		echo "(!) You are not root. This command requires 'sudo -E' \n"; \
	fi

_docker-build-onem2m:
	@echo "Starting to build the oneM2M testing tools.."

	# let's build the testing tool image (same for interop and conformance)
	docker build -t testing_tool-interoperability-onem2m-v$(version) -f envs/onem2m_testing_tool/Dockerfile .

	# tag all last version images also with a version-less name
	docker tag testing_tool-interoperability-onem2m-v$(version):latest testing_tool-interoperability-onem2m

_docker-build-6lowpan:
	@echo "Starting to build the 6lowpan testing tools.."

	# let's build the testing tool image (same for interop and conformance)
	docker build -t testing_tool-interoperability-6lowpan-v$(version) -f envs/6lowpan_testing_tool/Dockerfile .

	# tag all last version images also with a version-less name
	docker tag testing_tool-interoperability-6lowpan-v$(version):latest testing_tool-interoperability-6lowpan

_docker-build-coap:
	@echo "Starting to build coap testing tools.."

	# let's build the testing tool image (same for interop and conformance)
	docker build -t testing_tool-interoperability-coap-v$(version) -f envs/coap_testing_tool/Dockerfile .

	# the testing tool for interop and conformance are the same, so lets tag it as such
	docker tag testing_tool-interoperability-coap-v$(version):latest testing_tool-conformance-coap-v$(version)

	# tag all last version images also with a version-less name
	docker tag testing_tool-interoperability-coap-v$(version):latest testing_tool-interoperability-coap
	docker tag testing_tool-conformance-coap-v$(version):latest testing_tool-conformance-coap

_docker-build-coap-additional-resources:
	@echo "Starting to build coap-additional-resources.. "

	# let's build the automated/reference IUT images used by F-Interop platform
	docker build -t automated_iut-coap_server-californium-v$(version) -f automated_IUTs/coap_server_californium/Dockerfile . --no-cache
	docker build -t automated_iut-coap_client-californium-v$(version) -f automated_IUTs/coap_client_californium/Dockerfile . --no-cache
	docker build -t automated_iut-coap_server-coapthon-v$(version) -f automated_IUTs/coap_server_coapthon/Dockerfile .
	docker build -t automated_iut-coap_client-coapthon-v$(version) -f automated_IUTs/coap_client_coapthon/Dockerfile .

	docker tag automated_iut-coap_client-coapthon-v$(version):latest automated_iut-coap_client-coapthon
	docker tag automated_iut-coap_server-coapthon-v$(version):latest automated_iut-coap_server-coapthon

	docker tag automated_iut-coap_client-californium-v$(version):latest automated_iut-coap_client-californium
	docker tag automated_iut-coap_server-californium-v$(version):latest automated_iut-coap_server-californium

	docker tag automated_iut-coap_client-coapthon-v$(version):latest reference_iut-coap_client
	docker tag automated_iut-coap_server-californium-v$(version):latest reference_iut-coap_server

info_message = """ \\n\
	******************************************************************************************\n\
	docker images naming must follow the following conventions: \n\
	\n\
	resource_type-sub_type-resource_name-version \n\
	\n\
	resource_type, sub_type and resource_name cannot contain any special character, nor  '-' \n\
	version format must comply to vx.x \n\
	\n\
	examples: \n\
	\n\
	automated_iut-coap_client-coapthon-v$(version) \n\
	automated_iut-coap_server-californium-v$(version) \n\
	\n\
	testing_tool-performance-coap-v$(version) \n\
	testing_tool-interoperability-coap-v$(version) \n\
	testing_tool-interoperability-coap (alias to last version) \n\
	testing_tool-conformance-coap-v$(version) \n\
	testing_tool-conformance-coap (alias to last version) \n\
	testing_tool-conformance-6tisch-v$(version) \n\
	\n\
	reference_iut-coap_client (alias) \n\
	reference_iut-coap_server (alias) \n\
	******************************************************************************************\n\\n\
	"""