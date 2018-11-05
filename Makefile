version = 1.0

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
	automated_iut-coap_client-coapthon \n\
	automated_iut-coap_server-californium \n\
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

LIST = automated_iut-coap_client-coapthon \
	   automated_iut-coap_client-aiocoap \
	   automated_iut-coap_client-libcoap \
	   automated_iut-coap_client-californium \
	   automated_iut-coap_server-coapthon \
	   automated_iut-coap_server-august_cellars \
	   automated_iut-coap_server-californium \
	   testing_tool-interoperability-coap \
	   testing_tool-interoperability-comi \
	   testing_tool-interoperability-6lowpan \
	   testing_tool-interoperability-onem2m \
	   testing_tool-interoperability-lwm2m \
	   reference_iut-coap_server \
	   reference_iut-coap_client \
           automated_iut-onem2m_adn \
           automated_iut-onem2m_server-eclipse_om2m \
	   automated_iut-lwm2m_server-leshan \
	   automated_iut-lwm2m_client-leshan \


info:
	@echo $(info_message)

version:
	@echo ioppytest v$(version)

echo_amqp_env_params:
	@echo URL: $(AMQP_URL)
	@echo EXCHANGE: $(AMQP_EXCHANGE)

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

# # # # Testing Tool & other resources BUILD commands # # # #
build-all-coap-images: ## Build all testing tool in docker images, and other docker image resources too
	@echo "Starting to build CoAP docker images.. "
	$(MAKE) _docker-build-coap
	$(MAKE) _docker-build-coap-additional-resources

build-tools: ## builds all testing tool docker images (only testing tool)
	@echo $(info_message)
	@echo "Starting to build docker images.. "
	$(MAKE) _docker-build-dummy-gui-adaptor
	$(MAKE) _docker-build-coap
	$(MAKE) _docker-build-6lowpan
	$(MAKE) _docker-build-onem2m
	$(MAKE) _docker-build-lwm2m
	$(MAKE) _docker-build-comi

build-automated-iuts: ## Build all automated-iut docker images
	@echo "Starting to build docker images.. "
	$(MAKE) _docker-build-coap-additional-resources
	$(MAKE) _docker-build-comi-additional-resources
	$(MAKE) _docker-build-onem2m-additional-resources
	$(MAKE) _docker-build-lwm2m-additional-resources

build-all: ## Build all testing tool in docker images, and other docker image resources too
	@echo $(info_message)
	@echo "Starting to build all docker images.. "
	$(MAKE) build-tools
	$(MAKE) build-automated-iuts

clean: ## clean data directory
	@echo "running $@"
	rm *.pcap
	rm data/results/*.json

# # # # Testing Tool & other resources RUN commands # # # #

sniff-bus: ## Listen and echo all messages in the event bus
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@python3 -m ioppytest_cli connect -ll

run-cli: ## Run interactive shell
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@python3 -m ioppytest_cli repl

run-6lowpan-testing-tool: ## Run 6LoWPAN testing tool in docker container
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-6lowpan testing_tool-interoperability-6lowpan

run-coap-testing-tool: ## Run CoAP testing tool in docker container
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-coap testing_tool-interoperability-coap

run-lwm2m-testing-tool: ## Run lwm2m testing tool in docker container
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-lwm2m testing_tool-interoperability-lwm2m

run-onem2m-testing-tool: ## Run oneM2M testing tool in docker container
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-onem2m testing_tool-interoperability-onem2m

run-comi-testing-tool: ## Run CoMI testing tool in docker container
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name testing_tool-interoperability-comi testing_tool-interoperability-comi

run-agent-coap-client: # TODO make a more generic command for any agent, then config phase happens later..
	$(MAKE) _check-sudo
	ioppytest-agent connect --url $(AMQP_URL) --exchange $(AMQP_EXCHANGE)  --name coap_client

run-agent-coap-server:
	$(MAKE) _check-sudo
	ioppytest-agent connect --url $(AMQP_URL) --exchange $(AMQP_EXCHANGE)  --name coap_server

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

stop-lwm2m-testing-tool:
	docker stop testing_tool-interoperability-lwm2m

stop-6lowpan-testing-tool:
	docker stop testing_tool-interoperability-6lowpan

stop-coap-testing-tool:
	docker stop testing_tool-interoperability-coap

stop-coap-server:
	docker stop reference_iut-coap_server

stop-coap-client:
	docker stop reference_iut-coap_client

stop-coap-client-californium:
	docker stop automated_iut-coap_client-californium

stop-coap-server-californium:
	docker stop automated_iut-coap_server-californium

stop-coap-client-coapthon:
	docker stop automated_iut-coap_client-coapthon

stop-coap-server-coapthon:
	docker stop automated_iut-coap_server-coapthon

stop-coap-client-aiocoap:
	docker stop automated_iut-coap_client-aiocoap

stop-coap-client-libcoap:
	docker stop automated_iut-coap_client-libcoap

stop-coap-server-august_cellars:
	docker stop automated_iut-coap_server-august_cellars

stop-all: ## stops testing tools and IUTs running as docker containers
	@echo "Stoppping all running containers spawned by ioppytest..."
	@- $(foreach LIST,$(LIST), \
		docker stop "$(word 1,$(subst :, ,$(LIST)))" ; \
    ) exit 0

# # # # UNITTEST commands # # # #

validate-test-description-syntax: ## validate (yaml) test description file syntax
	@python3 -m pytest -p no:cacheprovider tests/test_test_descriptions.py -vvv

run-tests: ## runs all unittests
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@python3 -m pytest -p no:cacheprovider tests/ -vvv

get-logs: ## echoes logs from the running containers
	@- $(foreach LIST,$(LIST), \
		echo "LOGS BEGIN >>>> $(word 1,$(subst :, ,$(LIST))) " ; \
		docker logs "$(word 1,$(subst :, ,$(LIST)))" ; \
		echo "LOGS END <<<<< $(word 1,$(subst :, ,$(LIST))) " \
    ); exit 0

install-python-dependencies: ## installs all py2 and py3 pip dependencies
	@echo "installing py2 submodule's dependencies..."
	@python -m pip -qq install ioppytest-agent

	@echo "installing py3 submodule's dependencies..."
	@python3 -m pip -qq install ioppytest-utils

	@echo "installing py3 ioppytest's dependencies..."
	@python3 -m pip -qq install -r ioppytest/requirements.txt
	@python3 -m pip -qq install -r automation/requirements.txt

# # # # other AUXILIARY commands  # # # #
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

_docker-build-lwm2m:
	@echo "Starting to build the lwm2m testing tools.."

	# let's build the testing tool image (same for interop and conformance)
	docker build --quiet -t testing_tool-interoperability-lwm2m-v$(version) -f envs/lwm2m_testing_tool/Dockerfile .

	# tag all last version images also with a version-less name
	docker tag testing_tool-interoperability-lwm2m-v$(version):latest testing_tool-interoperability-lwm2m

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

	# automated_iut-coap_server-californium  & automated_iut-coap_client-californium
	# build without using caché packages (slower builds)
	docker build --quiet -t automated_iut-coap_server-californium-v$(version) -f automation/coap_server_californium/Dockerfile . --no-cache
	#docker build --quiet -t automated_iut-coap_client-californium-v$(version) -f automation/coap_client_californium/Dockerfile . --no-cache

	# automated_iut-coap_server-californium  & automated_iut-coap_client-californium
	#docker build --quiet -t automated_iut-coap_server-californium-v$(version) -f automation/coap_server_californium/Dockerfile .
	docker build --quiet -t automated_iut-coap_client-californium-v$(version) -f automation/coap_client_californium/Dockerfile .
	docker tag automated_iut-coap_client-californium-v$(version):latest automated_iut-coap_client-californium
	docker tag automated_iut-coap_server-californium-v$(version):latest automated_iut-coap_server-californium
	docker tag automated_iut-coap_client-californium-v$(version):latest reference_iut-coap_client
	docker tag automated_iut-coap_server-californium-v$(version):latest reference_iut-coap_server

	# automated_iut-coap_server-coapthon & automated_iut-coap_client-coapthon
	docker build --quiet -t automated_iut-coap_server-coapthon-v$(version) -f automation/coap_server_coapthon/Dockerfile .
	docker build --quiet -t automated_iut-coap_client-coapthon-v$(version) -f automation/coap_client_coapthon/Dockerfile .
	docker tag automated_iut-coap_client-coapthon-v$(version):latest automated_iut-coap_client-coapthon
	docker tag automated_iut-coap_server-coapthon-v$(version):latest automated_iut-coap_server-coapthon

	# automated_iut-coap_client-aiocoap
	docker build --quiet -t automated_iut-coap_client-aiocoap-v$(version) -f automation/coap_client_aiocoap/Dockerfile .
	docker tag automated_iut-coap_client-aiocoap-v$(version):latest automated_iut-coap_client-aiocoap

	# automated_iut-coap_client-libcoap
	docker build --quiet -t automated_iut-coap_client-libcoap-v$(version) -f automation/coap_client_libcoap/Dockerfile .
	docker tag automated_iut-coap_client-libcoap-v$(version):latest automated_iut-coap_client-libcoap

	# automated_iut-coap_server-august_cellars (WIP)
	docker build --quiet -t automated_iut-coap_server-august_cellars-v$(version) -f automation/coap_server_august_cellars/Dockerfile .
	docker tag automated_iut-coap_server-august_cellars-v$(version):latest automated_iut-coap_server-august_cellars

_docker-build-lwm2m-additional-resources:
	@echo "Starting to build lwm2m-additional-resources.. "
	docker build --quiet -t automated_iut-lwm2m_client-leshan-v$(version) -f automation/lwm2m_client_leshan/Dockerfile .
	docker build --quiet -t automated_iut-lwm2m_server-leshan-v$(version) -f automation/lwm2m_server_leshan/Dockerfile .

	docker tag automated_iut-lwm2m_client-leshan-v$(version):latest automated_iut-lwm2m_client-leshan
	docker tag automated_iut-lwm2m_server-leshan-v$(version):latest automated_iut-lwm2m_server-leshan

_docker-build-onem2m-additional-resources:
	@echo "Starting to build onem2m-additional-resources.. "
	
	docker build --quiet -t automated_iut-onem2m_server-eclipse_om2m-v$(version) -f automation/onem2m_cse_eclipse_om2m/Dockerfile .
	docker tag automated_iut-onem2m_server-eclipse_om2m-v$(version):latest automated_iut-onem2m_server-eclipse_om2m
        
	docker build --quiet -t automated_iut-onem2m_adn-v$(version) -f automation/onem2m_adn_etsi_implementation/Dockerfile .
	docker tag automated_iut-onem2m_adn-v$(version):latest automated_iut-onem2m_adn
	
_docker-build-comi-additional-resources:
	@echo "Starting to build comi-additional-resources.. "
	docker build --quiet -t automated_iut-comi_server-acklio-v$(version) -f automation/comi_server_acklio/Dockerfile .
	docker tag automated_iut-comi_server-acklio-v$(version):latest automated_iut-comi_server-acklio

	docker build --quiet -t automated_iut-comi_client-acklio-v$(version) -f automation/comi_client_acklio/Dockerfile .
	docker tag automated_iut-comi_client-acklio-v$(version):latest automated_iut-comi_client-acklio

_docker-build-6lowpan-additional-resources:
	@echo "Starting to build 6lowpan-additional-resources.. "
	@echo "TBD"


# # # # running fully-automated interop tests commands  # # # #

_setup-coap-mini-interop-californium-cli-vs-californium-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-californium automated_iut-coap_client-californium
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-californium automated_iut-coap_server-californium

_setup-coap-mini-interop-aiocoap-cli-vs-californium-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-aiocoap automated_iut-coap_client-aiocoap
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-californium automated_iut-coap_server-californium

_setup-coap-mini-interop-libcoap-cli-vs-californium-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-libcoap automated_iut-coap_client-libcoap
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-californium automated_iut-coap_server-californium

_setup-coap-mini-interop-libcoap-cli-vs-august_cellars-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-libcoap automated_iut-coap_client-libcoap
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-august_cellars automated_iut-coap_server-august_cellars

_run-coap-mini-interop-libcoap-cli-vs-august-cellars-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	$(MAKE) run-coap-testing-tool
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-libcoap automated_iut-coap_client-libcoap
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-august_cellars automated_iut-coap_server-august_cellars

_run-coap-mini-interop-aiocoap-cli-vs-august_cellars-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	$(MAKE) run-coap-testing-tool
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-aiocoap automated_iut-coap_client-aiocoap
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-august_cellars automated_iut-coap_server-august_cellars


_run-coap-mini-interop-aiocoap-cli-vs-coapthon-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	$(MAKE) run-coap-testing-tool
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-aiocoap automated_iut-coap_client-aiocoap
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-coapthon automated_iut-coap_server-coapthon

_run-coap-mini-interop-californium-cli-vs-californium-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	$(MAKE) run-coap-testing-tool
	$(MAKE) _setup-coap-mini-interop-californium-cli-vs-californium-server

_run-coap-mini-interop-aiocoap-cli-vs-californium-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	$(MAKE) run-coap-testing-tool
	$(MAKE) _setup-coap-mini-interop-aiocoap-cli-vs-californium-server

_run-coap-mini-interop-libcoap-cli-vs-californium-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	$(MAKE) run-coap-testing-tool
	$(MAKE) _setup-coap-mini-interop-libcoap-cli-vs-californium-server

_run-coap-mini-interop-libcoap-cli-vs-august_cellars-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	$(MAKE) run-coap-testing-tool
	$(MAKE) _setup-coap-mini-interop-libcoap-cli-vs-august_cellars-server

_run-lwm2m-mini-interop-leshan-cli-vs-leshan-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	$(MAKE) run-lwm2m-testing-tool
	$(MAKE) _setup-coap-mini-interop-leshan-cli-vs-leshan-server

_setup-coap-mini-interop-leshan-cli-vs-leshan-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-lwm2m_client-leshan automated_iut-lwm2m_client-leshan
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-lwm2m_server-leshan automated_iut-lwm2m_server-leshan

_setup-coap-mini-interop-californium-cli-vs-coapthon-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-californium automated_iut-coap_client-californium
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-coapthon automated_iut-coap_server-coapthon

_run-coap-mini-interop-californium-cli-vs-coapthon-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	$(MAKE) run-coap-testing-tool
	$(MAKE) _setup-coap-mini-interop-californium-cli-vs-coapthon-server

_setup-coap-mini-interop-coapthon-cli-vs-coapthon-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-coapthon automated_iut-coap_client-coapthon
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-coapthon automated_iut-coap_server-coapthon

_run-coap-mini-interop-coapthon-cli-vs-coapthon-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	$(MAKE) run-coap-testing-tool
	$(MAKE) _setup-coap-mini-interop-coapthon-cli-vs-coapthon-server

_setup-coap-mini-interop-coapthon-cli-vs-californium-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_client-coapthon automated_iut-coap_client-coapthon
	docker run -d --rm  --env AMQP_EXCHANGE=$(AMQP_EXCHANGE) --env AMQP_URL=$(AMQP_URL) --sysctl net.ipv6.conf.all.disable_ipv6=0 --privileged --name automated_iut-coap_server-californium automated_iut-coap_server-californium

_run-coap-mini-interop-coapthon-cli-vs-californium-server:
	@echo "Using AMQP env vars: {url : $(AMQP_URL), exchange : $(AMQP_EXCHANGE)}"
	@echo "running $@"
	$(MAKE) run-coap-testing-tool
	$(MAKE) _setup-coap-mini-interop-coapthon-cli-vs-californium-server

_stop-coap-mini-interop-coapthon-cli-vs-californium-server:
	$(MAKE) stop-coap-client-coapthon
	$(MAKE) stop-coap-server-californium
	$(MAKE) stop-coap-testing-tool

_stop-coap-mini-interop-californium-cli-vs-californium-server:
	$(MAKE) stop-coap-client-californium
	$(MAKE) stop-coap-server-californium
	$(MAKE) stop-coap-testing-tool

_stop-coap-mini-interop-californium-cli-vs-coapthon-server:
	$(MAKE) stop-coap-client-californium
	$(MAKE) stop-coap-server-coapthon
	$(MAKE) stop-coap-testing-tool

_stop-coap-mini-interop-coapthon-cli-vs-coapthon-server:
	$(MAKE) stop-coap-client-coapthon
	$(MAKE) stop-coap-server-coapthon
	$(MAKE) stop-coap-testing-tool




