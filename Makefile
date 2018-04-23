version = 1.0

info:
	@echo $(info_message)

version:
	@echo ioppytest v$(version)


help: ## Help dialog.
	@IFS=$$'\n' ; \
	help_lines=(`fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//'`); \
	for help_line in $${help_lines[@]}; do \
		IFS=$$'#' ; \
		help_split=($$help_line) ; \
		help_command=`echo $${help_split[0]} | sed -e 's/^ *//' -e 's/ *$$//'` ; \
		help_info=`echo $${help_split[2]} | sed -e 's/^ *//' -e 's/ *$$//'` ; \
		printf "%-30s %s\n" $$help_command $$help_info ; \
	done

build-tools: ## builds all testing tool docker images (only testing tool)
	@echo $(info_message)
	@echo "Starting to build docker images.. "
	$(MAKE) _docker-build-dummy-gui-adaptor
	$(MAKE) _docker-build-coap
	$(MAKE) _docker-build-6lowpan
	$(MAKE) _docker-build-onem2m
	$(MAKE) _docker-build-comi

build-automated-iuts: ## Build all automated-iut docker images
	@echo "Starting to build docker images.. "
	$(MAKE) _docker-build-coap-additional-resources
	$(MAKE) _docker-build-comi-additional-resources
	$(MAKE) _docker-build-onem2m-additional-resources

build-all: ## Build all testing tool in docker images, and other docker image resources too
	@echo $(info_message)
	@echo "Starting to build all docker images.. "
	$(MAKE) build-tools
	$(MAKE) build-automated-iuts

sniff-bus: ## Listen and echo all messages in the event bus
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@python3 -m ioppytest.utils.interop_cli connect -ll

run-cli: ## Run interactive shell
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@python3 -m ioppytest.utils.interop_cli repl

run-6lowpan-testing-tool: ## Run 6LoWPAN testing tool in docker container
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-6lowpan testing_tool-interoperability-6lowpan

run-coap-testing-tool: ## Run CoAP testing tool in docker container
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-coap testing_tool-interoperability-coap

run-onem2m-testing-tool: ## Run oneM2M testing tool in docker container
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-onem2m testing_tool-interoperability-onem2m

run-comi-testing-tool: ## Run CoMI testing tool in docker container
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-comi testing_tool-interoperability-comi

run-agent-coap-client: # TODO make a more generic command for any agent, then config phase happens later..
	$(MAKE) _check-sudo
	cd ioppytest/agent && python agent.py connect --url $(AMQP_URL) --exchange $(AMQP_EXCHANGE)  --name coap_client

run-agent-coap-server:
	$(MAKE) _check-sudo
	cd ioppytest/agent && python agent.py connect --url $(AMQP_URL) --exchange $(AMQP_EXCHANGE)  --name coap_server

run-coap-client:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name reference_iut-coap_client reference_iut-coap_client

run-coap-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d -t --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name reference_iut-coap_server reference_iut-coap_server

stop-comi-testing-tool:
	docker stop testing_tool-interoperability-comi

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

stop-coap-client-californium:
	docker stop automated_iut-coap_client-californium-v$(version)

stop-coap-server-californium:
	docker stop automated_iut-coap_server-californium-v$(version)

stop-coap-client-coapthon:
	docker stop automated_iut-coap_client-coapthon-v$(version)

stop-coap-server-coapthon:
	docker stop automated_iut-coap_server-coapthon-v$(version)

stop-all: ## Stop testing tools running as docker containers
	@echo "running $@"
	# (exit 0) -> so the script continues on errors
	$(MAKE) stop-coap-testing-tool --keep-going ; exit 0
	$(MAKE) stop-6lowpan-testing-tool --keep-going ; exit 0
	$(MAKE) stop-coap-server --keep-going ; exit 0
	$(MAKE) stop-coap-client --keep-going ; exit 0
	$(MAKE) stop-coap-client-californium --keep-going ; exit 0
	$(MAKE) stop-coap-server-californium --keep-going ; exit 0
	$(MAKE) stop-coap-client-coapthon --keep-going ; exit 0
	$(MAKE) stop-coap-server-coapthon --keep-going ; exit 0

validate-test-description-syntax: ## validate (yaml) test description file syntax
	@python3 -m pytest -p no:cacheprovider ioppytest/extended_test_descriptions/tests/tests.py -vvv

run-tests: ## runs all unittests
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@python3 -m pytest -p no:cacheprovider ioppytest/extended_test_descriptions/tests/tests.py -vvv
	@python3 -m pytest -p no:cacheprovider ioppytest/test_coordinator/tests/tests.py -vvv
	@python3 -m pytest -p no:cacheprovider ioppytest/packet_router/tests/tests.py -vvv
	@python3 -m pytest -p no:cacheprovider ioppytest/sniffer/tests/__init__.py -vvv
	$(MAKE) _test_submodules


_test_ttproto:
	cd ioppytest/test_analysis_tool ;python3 -m pytest -p no:cacheprovider tests/test_core --ignore=tests/test_core/test_dissector/test_dissector_6lowpan.py
	
_test_utils:
	cd ioppytest/utils ;python3 -m pytest -p no:cacheprovider tests
	
_test_submodules:
	@echo "TODO: run ttproto tests as well once they are ok"
	# $(MAKE) _test_ttproto
	$(MAKE) _test_utils
	

get-logs: ## Get logs from the running containers
	@echo ">>>>> start logs testing_tool-interoperability-coap"
	docker logs testing_tool-interoperability-coap ; exit 0
	@echo "<<<<< end logs testing_tool-interoperability-coap \n"

	@echo ">>>>> start logs testing_tool-interoperability-6lowpan"
	docker logs testing_tool-interoperability-6lowpan ; exit 0
	@echo "<<<<< end logs testing_tool-interoperability-6lowpan \n"

	@echo ">>>>> start logs testing_tool-interoperability-onem2m"
	docker logs testing_tool-interoperability-onem2m ; exit 0
	@echo "<<<<< end logs testing_tool-interoperability-onem2m \n"

	@echo ">>>>> start logs reference_iut-coap_server"
	docker logs reference_iut-coap_server ; exit 0
	@echo "<<<<< end logs reference_iut-coap_server \n"

	@echo ">>>>> start logs reference_iut-coap_client"
	docker logs reference_iut-coap_client ; exit 0
	@echo "<<<<< end logs reference_iut-coap_client \n"

install-python-dependencies: ## installs all python pip dependencies
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

_docker-build-dummy-gui-adaptor:
	@echo "Starting to build the dummy-gui-adaptor.."

	# let's build the testing tool image (same for interop and conformance)
	docker build --quiet -t  dummy-gui-adaptor -f envs/dummy_testing_tool/Dockerfile .

_docker-build-onem2m:
	@echo "Starting to build the oneM2M testing tools.."

	# let's build the testing tool image (same for interop and conformance)
	docker build --quiet -t testing_tool-interoperability-onem2m-v$(version) -f envs/onem2m_testing_tool/Dockerfile .

	# tag all last version images also with a version-less name
	docker tag testing_tool-interoperability-onem2m-v$(version):latest testing_tool-interoperability-onem2m

_docker-build-6lowpan:
	@echo "Starting to build the 6lowpan testing tools.."

	# let's build the testing tool image (same for interop and conformance)
	docker build --quiet -t testing_tool-interoperability-6lowpan-v$(version) -f envs/6lowpan_testing_tool/Dockerfile .

	# tag all last version images also with a version-less name
	docker tag testing_tool-interoperability-6lowpan-v$(version):latest testing_tool-interoperability-6lowpan

_docker-build-comi:
	@echo "Starting to build CoMI testing tools.."

	# let's build the testing tool image (same for interop and conformance)
	docker build --quiet -t testing_tool-interoperability-comi-v$(version) -f envs/comi_testing_tool/Dockerfile .

	# tag all last version images also with a version-less name
	docker tag testing_tool-interoperability-comi-v$(version):latest testing_tool-interoperability-comi

_docker-build-coap:
	@echo "Starting to build coap testing tools.."

	# let's build the testing tool image (same for interop and conformance)
	docker build --quiet -t testing_tool-interoperability-coap-v$(version) -f envs/coap_testing_tool/Dockerfile .

	# the testing tool for interop and conformance are the same, so lets tag it as such
	docker tag testing_tool-interoperability-coap-v$(version):latest testing_tool-conformance-coap-v$(version)

	# tag all last version images also with a version-less name
	docker tag testing_tool-interoperability-coap-v$(version):latest testing_tool-interoperability-coap
	docker tag testing_tool-conformance-coap-v$(version):latest testing_tool-conformance-coap

_docker-build-coap-additional-resources:
	@echo "Starting to build coap-additional-resources.. "

	# let's build the automated/reference IUT images used by F-Interop platform

	# build without using caché packages (slower builds)
	# docker build --quiet -t automated_iut-coap_server-californium-v$(version) -f automated_IUTs/coap_server_californium/Dockerfile . --no-cache
	# docker build --quiet -t automated_iut-coap_client-californium-v$(version) -f automated_IUTs/coap_client_californium/Dockerfile . --no-cache

	docker build --quiet -t automated_iut-coap_server-californium-v$(version) -f automated_IUTs/coap_server_californium/Dockerfile .
	docker build --quiet -t automated_iut-coap_client-californium-v$(version) -f automated_IUTs/coap_client_californium/Dockerfile .

	docker build --quiet -t automated_iut-coap_server-coapthon-v$(version) -f automated_IUTs/coap_server_coapthon/Dockerfile .
	docker build --quiet -t automated_iut-coap_client-coapthon-v$(version) -f automated_IUTs/coap_client_coapthon/Dockerfile .

	docker tag automated_iut-coap_client-coapthon-v$(version):latest automated_iut-coap_client-coapthon
	docker tag automated_iut-coap_server-coapthon-v$(version):latest automated_iut-coap_server-coapthon

	docker tag automated_iut-coap_client-californium-v$(version):latest automated_iut-coap_client-californium
	docker tag automated_iut-coap_server-californium-v$(version):latest automated_iut-coap_server-californium

	docker tag automated_iut-coap_client-coapthon-v$(version):latest reference_iut-coap_client
	docker tag automated_iut-coap_server-californium-v$(version):latest reference_iut-coap_server

_docker-build-onem2m-additional-resources:
	@echo "Starting to build onem2m-additional-resources.. "
	@echo "TBD"

_docker-build-comi-additional-resources:
	@echo "Starting to build comi-additional-resources.. "
	docker build --quiet -t automated_iut-comi_server-acklio-v$(version) -f automated_IUTs/comi_server_acklio/Dockerfile .
	docker tag automated_iut-comi_server-acklio-v$(version):latest automated_iut-comi_server-acklio

	docker build --quiet -t automated_iut-comi_client-acklio-v$(version) -f automated_IUTs/comi_client_acklio/Dockerfile .
	docker tag automated_iut-comi_client-acklio-v$(version):latest automated_iut-comi_client-acklio

_docker-build-6lowpan-additional-resources:
	@echo "Starting to build 6lowpan-additional-resources.. "
	@echo "TBD"

_run-coap-mini-plugfest-californium-cli-vs-californium-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"

	$(MAKE) run-coap-testing-tool

	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-californium-v$(version) automated_iut-coap_client-californium-v$(version)
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-californium-v$(version) automated_iut-coap_server-californium-v$(version)

_run-coap-mini-plugfest-californium-cli-vs-coapthon-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"

	$(MAKE) run-coap-testing-tool

	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-californium-v$(version) automated_iut-coap_client-californium-v$(version)
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-coapthon-v$(version) automated_iut-coap_server-coapthon-v$(version)

_run-coap-mini-plugfest-coapthon-cli-vs-coapthon-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"

	$(MAKE) run-coap-testing-tool

	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-coapthon-v$(version) automated_iut-coap_client-coapthon-v$(version)
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-coapthon-v$(version) automated_iut-coap_server-coapthon-v$(version)


_run-coap-mini-plugfest-coapthon-cli-vs-californium-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"

	$(MAKE) run-coap-testing-tool

	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-coapthon-v$(version) automated_iut-coap_client-coapthon-v$(version)
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-californium-v$(version) automated_iut-coap_server-californium-v$(version)


_stop-coap-mini-plugfest-coapthon-cli-vs-californium-server:
	$(MAKE) stop-coap-client-coapthon
	$(MAKE) stop-coap-server-californium
	$(MAKE) stop-coap-testing-tool

_stop-coap-mini-plugfest-californium-cli-vs-californium-server:
	$(MAKE) stop-coap-client-californium
	$(MAKE) stop-coap-server-californium
	$(MAKE) stop-coap-testing-tool

_stop-coap-mini-plugfest-californium-cli-vs-coapthon-server:
	$(MAKE) stop-coap-client-californium
	$(MAKE) stop-coap-server-coapthon
	$(MAKE) stop-coap-testing-tool

_stop-coap-mini-plugfest-coapthon-cli-vs-coapthon-server:
	$(MAKE) stop-coap-client-coapthon
	$(MAKE) stop-coap-server-coapthon
	$(MAKE) stop-coap-testing-tool



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
