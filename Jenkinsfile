properties([[$class: 'GitLabConnectionProperty', gitLabConnection: 'figitlab']])

if(env.JOB_NAME =~ 'ioppytest-unitests-and-integration-tests/'){
    node('docker'){
        env.AMQP_URL="amqp://guest:guest@localhost/"
        env.AMQP_EXCHANGE="amq.topic"

        stage("Clone repo and submodules"){
            checkout scm
            sh '''
                git submodule update --init
                # tree .
            '''
        }

        stage ("Environment dependencies"){
            withEnv(["DEBIAN_FRONTEND=noninteractive"]){
                sh '''
                    sudo apt-get clean
                    sudo apt-get update
                    sudo apt-get upgrade -y -qq
                    sudo apt-get install --fix-missing -y -qq python-dev python-pip python-setuptools
                    sudo apt-get install --fix-missing -y -qq python3-dev python3-pip python3-setuptools
                    sudo apt-get install --fix-missing -y -qq build-essential
                    sudo apt-get install --fix-missing -y -qq libyaml-dev
                    sudo apt-get install --fix-missing -y -qq libssl-dev openssl
                    sudo apt-get install --fix-missing -y -qq libffi-dev
                    sudo apt-get install --fix-missing -y -qq curl tree netcat
                    sudo apt-get install --fix-missing -y -qq rabbitmq-server
                    sudo apt-get install --fix-missing -y -qq supervisor
                    sudo apt-get install --fix-missing -y -qq make

                    echo restarting rmq server and app
                    sudo rabbitmq-server -detached || true
                    sudo rabbitmqctl stop_app || true
                    sudo rabbitmqctl start_app || true
                '''

          }
      }

      stage("Testing Tool dependencies"){
        gitlabCommitStatus("Testing Tool dependencies"){
            withEnv(["DEBIAN_FRONTEND=noninteractive"]){
            sh '''
                echo installing python dependencies...
                sudo -H make install-python-dependencies
            '''
            }
        }
      }

      stage("install-development-environment-dependencies"){
        withEnv(["DEBIAN_FRONTEND=noninteractive"]){
            sh '''
                # TODO make a install-devopment-environment-dependencies in Makefile
                #sudo -H make install-devopment-environment-dependencies

                echo installing other dependencies needed for running tests

                # Install autogen dependencies
                sudo -H apt-get -y install autoconf
                sudo -H apt-get -y install pkg-config
                sudo -H apt-get -y install libtool
                sudo -H apt-get -y install autotools-dev
                sudo -H apt-get -y install automake

                # Install libcoap API & CLI from sources
	            git clone https://github.com/obgm/libcoap.git /tmp/libcoap_git
	            cd /tmp/libcoap_git
	            ./autogen.sh
	            ./configure --enable-examples --disable-doxygen --disable-manpages
	            sudo make
	            sudo make install
	            export PATH="/tmp/libcoap_gitgit/examples:$PATH"
	            export LD_LIBRARY_PATH=/usr/local/lib
            '''
        }
      }


      stage("test description (yaml files) validation"){
        gitlabCommitStatus("test description (yaml files) validation"){
            sh '''
                make validate-test-description-syntax
            '''
        }
      }

      stage("unittesting components"){
        gitlabCommitStatus("unittesting components"){
            sh '''
                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                make run-tests
            '''
        }
      }

      stage("Functional tests / AMQP API smoke tests"){
        env.SUPERVISOR_CONFIG_FILE="envs/coap_testing_tool/tests.supervisor.conf.ini"
        gitlabCommitStatus("Functional tests / AMQP API smoke tests"){
            try {
                sh '''
                    echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                    sudo -E supervisord -c $SUPERVISOR_CONFIG_FILE
                    sleep 15

                    sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE status
                    python3 -m pytest -p no:cacheprovider tests/black_box_test___test_testing_tool_event_bus_api.py -v
                '''
          }
          catch (e){
            sh '''
                echo Do you smell the smoke in the room??
                echo processes logs :
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE tail -10000 tat
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE tail -100000 test-coordinator
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE tail -10000 agent
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE tail -10000 packet-router
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE tail -10000 packet-sniffer
            '''
            throw e
          }
          finally {
            sh'''
                sleep 5
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE status
                sleep 5
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE stop all
                sleep 5
            '''
          }
        }
      }
    }
}


if(env.JOB_NAME =~ 'ioppytest-lwm2m-implementation-continuous-testing/'){
    node('docker'){

        /* attention, here we use external RMQ server*/
        /* if integration tests take too long to execute we need to allow docker containers to access localhost's ports (docker host ports), and change AMQP_URL */

        env.AMQP_URL="amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/jenkins.lwm2m_implementations_continuous_testing"
        env.AMQP_EXCHANGE="amq.topic"
        env.DOCKER_CLIENT_TIMEOUT=3000
        env.COMPOSE_HTTP_TIMEOUT=3000

        /*This will tell the continuous-testing autoamtion code to run all test cases!*/
        env.CI = "True"

        stage("Check if DOCKER is installed on node"){
            sh '''
                docker version
            '''
        }

        stage("Clone repo and submodules"){
            checkout scm
            sh '''
                git submodule update --init
                tree .
            '''
        }

        stage("Install python dependencies"){
            gitlabCommitStatus("Install python dependencies"){
                withEnv(["DEBIAN_FRONTEND=noninteractive"]){
                    sh '''
                        sudo apt-get clean
                        sudo apt-get update
                        sudo apt-get upgrade -y -qq
                        sudo apt-get install --fix-missing -y -qq python-dev python-pip python-setuptools
                        sudo apt-get install --fix-missing -y -qq python3-dev python3-pip python3-setuptools
                        sudo apt-get install --fix-missing -y -qq build-essential
                        sudo apt-get install --fix-missing -y -qq libyaml-dev
                        sudo apt-get install --fix-missing -y -qq libssl-dev openssl
                        sudo apt-get install --fix-missing -y -qq libffi-dev
                        sudo apt-get install --fix-missing -y -qq make

                        sudo make install-python-dependencies
                    '''
                }
            }
        }

        stage("CONT_INTEROP_TESTS_1: Build docker images."){
            gitlabCommitStatus("BUILD lwm2m docker images") {
                sh '''
                    sudo -E make _docker-build-lwm2m
                    sudo -E make _docker-build-lwm2m-additional-resources
                    sudo -E docker images
                '''
            }
        }

        stage("CONT_INTEROP_TESTS_1: lwm2m_client VS lwm2m_server"){
            gitlabCommitStatus("Starting resources..") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        sh '''
                            sudo -E make clean 2>/dev/null
                           '''
                        }
                    catch (err) {
                        echo "something failed trying to clean repo"
                        }

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make _run-lwm2m-mini-interop-leshan-cli-vs-leshan-server
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
            }

            gitlabCommitStatus("Starting tests..") {
                long timeoutInSeconds = 600
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh '''
                            echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                            python3 -m automation.automated_interop
                        '''
                    }
                }
                catch (e){
                    sh '''
                        echo Do you smell the smoke in the room??
                        echo docker container logs :
                        sudo make get-logs
                    '''
                    throw e
                }
                finally {

                    sh '''
                        export LC_ALL=C.UTF-8
                        export LANG=C.UTF-8
                        python3 -m ioppytest_cli download_network_traces --destination .
                        sudo -E make stop-all
                        sudo -E docker ps
                    '''
                    archiveArtifacts artifacts: 'data/results/*.json', fingerprint: true
                    archiveArtifacts artifacts: '*.pcap', fingerprint: true
                }
            }
        }
    }
}


if(env.JOB_NAME =~ 'ioppytest-coap-implementation-continuous-testing/'){
    node('docker'){

        /* attention, here we use external RMQ server*/
        /* if integration tests take too long to execute we need to allow docker containers to access localhost's ports (docker host ports), and change AMQP_URL */

        env.AMQP_URL="amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/jenkins.coap_implementations_continuous_testing"
        env.AMQP_EXCHANGE="amq.topic"
        env.DOCKER_CLIENT_TIMEOUT=3000
        env.COMPOSE_HTTP_TIMEOUT=3000

        /*This will tell the continuous-testing autoamtion code to run all test cases!*/
        env.CI = "True"

        stage("Check if DOCKER is installed on node"){
            sh '''
                docker version
            '''
        }

        stage("Clone repo and submodules"){
            checkout scm
            sh '''
                git submodule update --init
                tree .
            '''
        }

        stage("Install python dependencies"){
            gitlabCommitStatus("Install python dependencies"){
                withEnv(["DEBIAN_FRONTEND=noninteractive"]){
                    sh '''
                        sudo apt-get clean
                        sudo apt-get update
                        sudo apt-get upgrade -y -qq
                        sudo apt-get install --fix-missing -y -qq python-dev python-pip python-setuptools
                        sudo apt-get install --fix-missing -y -qq python3-dev python3-pip python3-setuptools
                        sudo apt-get install --fix-missing -y -qq build-essential
                        sudo apt-get install --fix-missing -y -qq libyaml-dev
                        sudo apt-get install --fix-missing -y -qq libssl-dev openssl
                        sudo apt-get install --fix-missing -y -qq libffi-dev
                        sudo apt-get install --fix-missing -y -qq make

                        sudo make install-python-dependencies
                    '''
                }
            }
        }

        stage("CONT_INTEROP_TESTS_1: Build docker images."){
            gitlabCommitStatus("BUILD CoAP docker images") {
                sh '''
                    sudo -E docker build --quiet -t automated_iut-coap_server-californium -f automation/coap_server_californium/Dockerfile . --no-cache
                    sudo -E docker build --quiet -t automated_iut-coap_client-libcoap -f automation/coap_client_libcoap/Dockerfile . --no-cache
                    sudo -E docker build --quiet -t testing_tool-interoperability-coap -f envs/coap_testing_tool/Dockerfile . --no-cache
                    sudo -E docker images
                '''
            }
        }

        stage("CONT_INTEROP_TESTS_1: libcoap_clie VS californium_serv"){
            gitlabCommitStatus("Starting resources..") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        sh '''
                            sudo -E make clean 2>/dev/null
                           '''
                        }
                    catch (err) {
                        echo "something failed trying to clean repo"
                        }

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make _run-coap-mini-interop-libcoap-cli-vs-californium-server
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
            }

            gitlabCommitStatus("Starting tests..") {
                long timeoutInSeconds = 600
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh '''
                            echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                            python3 -m automation.automated_interop
                        '''
                    }
                }
                catch (e){
                    sh '''
                        echo Do you smell the smoke in the room??
                        echo docker container logs :
                        sudo make get-logs
                    '''
                    throw e
                }
                finally {

                    sh '''
                        export LC_ALL=C.UTF-8
                        export LANG=C.UTF-8
                        python3 -m ioppytest_cli download_network_traces --destination .
                        sudo -E make stop-all
                        sudo -E docker ps
                    '''
                    archiveArtifacts artifacts: 'data/results/*.json', fingerprint: true
                    archiveArtifacts artifacts: '*.pcap', fingerprint: true
                }
            }
        }

        stage("CONT_INTEROP_TESTS_2: Build docker images."){
            gitlabCommitStatus("BUILD CoAP docker images") {
                sh '''
                    sudo -E docker build --quiet -t automated_iut-coap_server-august_cellars -f automation/coap_server_august_cellars/Dockerfile .
                    sudo -E docker build --quiet -t automated_iut-coap_client-libcoap -f automation/coap_client_libcoap/Dockerfile .
                    sudo -E docker build --quiet -t testing_tool-interoperability-coap -f envs/coap_testing_tool/Dockerfile .
                    sudo -E docker images
                '''
            }
        }

        stage("CONT_INTEROP_TESTS_2: libcoap_clie VS august_cellars_serv"){
            gitlabCommitStatus("Starting resources..") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        sh '''
                            sudo -E make clean 2>/dev/null
                           '''
                        }
                    catch (err) {
                        echo "something failed trying to clean repo"
                        }

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make _run-coap-mini-interop-libcoap-cli-vs-august_cellars-server
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
            }

            gitlabCommitStatus("Starting tests..") {
                long timeoutInSeconds = 600
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh '''
                            echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                            python3 -m automation.automated_interop
                        '''
                    }
                }
                catch (e){
                    sh '''
                        echo Do you smell the smoke in the room??
                        echo docker container logs :
                        sudo make get-logs
                    '''
                    throw e
                }
                finally {

                    sh '''
                        export LC_ALL=C.UTF-8
                        export LANG=C.UTF-8
                        python3 -m ioppytest_cli download_network_traces --destination .
                        sudo -E make stop-all
                        sudo -E docker ps
                    '''
                    archiveArtifacts artifacts: 'data/results/*.json', fingerprint: true
                    archiveArtifacts artifacts: '*.pcap', fingerprint: true
                }
            }
        }
    }
}

if(env.JOB_NAME =~ 'ioppytest-coap-automated-iuts/'){
    node('docker'){

        /* attention, here we use external RMQ server*/
        /* if integration tests take too long to execute we need to allow docker containers to access localhost's ports (docker host ports), and change AMQP_URL */

        env.AMQP_URL="amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/jenkins.full_coap_interop_session"
        env.AMQP_EXCHANGE="amq.topic"
        env.DOCKER_CLIENT_TIMEOUT=3000
        env.COMPOSE_HTTP_TIMEOUT=3000

        stage("Check if DOCKER is installed on node"){
            sh '''
                docker version
            '''
        }

        stage("Clone repo and submodules"){
            checkout scm
            sh '''
                git submodule update --init
                # tree .
            '''
        }

        stage("Install python dependencies"){
            gitlabCommitStatus("Install python dependencies"){
                withEnv(["DEBIAN_FRONTEND=noninteractive"]){
                    sh '''
                        sudo apt-get clean
                        sudo apt-get update
                        sudo apt-get upgrade -y -qq
                        sudo apt-get install --fix-missing -y -qq python-dev python-pip python-setuptools
                        sudo apt-get install --fix-missing -y -qq python3-dev python3-pip python3-setuptools
                        sudo apt-get install --fix-missing -y -qq build-essential
                        sudo apt-get install --fix-missing -y -qq libyaml-dev
                        sudo apt-get install --fix-missing -y -qq libssl-dev openssl
                        sudo apt-get install --fix-missing -y -qq libffi-dev
                        sudo apt-get install --fix-missing -y -qq make

                        sudo make install-python-dependencies
                    '''
                }
            }
        }

        stage("BUILD CoAP docker images (testing tools and automated-iuts)"){
            gitlabCommitStatus("BUILD CoAP docker images (testing tools and automated-iuts)") {
                sh '''
                    sudo -E make build-all-coap-images
                    sudo -E docker images
                '''
            }
        }

        stage("RUN mini-plugtest: libcoap_clie VS august_cellars_serv"){
                    gitlabCommitStatus("START resources for mini-plugtest: libcoap_clie VS august_cellars_serv") {
                        gitlabCommitStatus("Docker run") {
                            long startTime = System.currentTimeMillis()
                            long timeoutInSeconds = 120

                            try {
                                timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                                    sh '''
                                        echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                        sudo -E make _run-coap-mini-interop-libcoap-cli-vs-august-cellars-server
                                    '''
                                }

                            } catch (err) {
                                long timePassed = System.currentTimeMillis() - startTime
                                if (timePassed >= timeoutInSeconds * 1000) {
                                    echo 'Docker container kept on running!'
                                    currentBuild.result = 'SUCCESS'
                                } else {
                                    currentBuild.result = 'FAILURE'
                                }
                            }
                        }
                    }
                    gitlabCommitStatus("EXECUTE mini-plugtest: libcoap_clie VS august_cellars_serv") {
                        long timeoutInSeconds = 600
                        try {
                            timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                                sh '''
                                    echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                    python3 -m pytest -s -p no:cacheprovider tests/integration_test__full_coap_interop_session.py -v
                                '''
                            }
                        }
                        catch (e){
                            sh '''
                                echo Do you smell the smoke in the room??
                                echo docker container logs :
                                sudo make get-logs
                            '''
                            throw e
                        }
                        finally {
                            sh '''
                                sudo -E make stop-all
                                sudo -E docker ps
                            '''
                        }
                    }
        }

        stage("RUN mini-plugtest: libcoap_clie VS californium_serv"){
            gitlabCommitStatus("START resources for mini-plugtest: libcoap_clie VS californium_serv") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make _run-coap-mini-interop-libcoap-cli-vs-californium-server
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
                }
            }
            gitlabCommitStatus("EXECUTE mini-plugtest: libcoap_clie VS californium_serv") {
                long timeoutInSeconds = 600
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh '''
                            echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                            python3 -m pytest -s -p no:cacheprovider tests/integration_test__full_coap_interop_session.py -v
                        '''
                    }
                }
                catch (e){
                    sh '''
                        echo Do you smell the smoke in the room??
                        echo docker container logs :
                        sudo make get-logs
                    '''
                    throw e
                }
                finally {
                    sh '''
                        sudo -E make stop-all
                        sudo -E docker ps
                    '''
                }
            }
        }
        
        stage("RUN mini-plugtest: aiocoap_clie VS californium_serv"){
            gitlabCommitStatus("START resources for mini-plugtest: aiocoap_clie VS californium_serv") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make _run-coap-mini-interop-aiocoap-cli-vs-californium-server
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
                }
            }
            gitlabCommitStatus("EXECUTE mini-plugtest: aiocoap_clie VS californium_serv") {
                long timeoutInSeconds = 600
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh '''
                            echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                            python3 -m pytest -s -p no:cacheprovider tests/integration_test__full_coap_interop_session.py -v
                        '''
                    }
                }
                catch (e){
                    sh '''
                        echo Do you smell the smoke in the room??
                        echo docker container logs :
                        sudo make get-logs
                    '''
                    throw e
                }
                finally {
                    sh '''
                        sudo -E make stop-all
                        sudo -E docker ps
                    '''
                }
            }
        }




       stage("RUN mini-plugtest: aiocoap_clie VS coaphton_serv"){
            gitlabCommitStatus("START resources for mini-plugtest: aiocoap_clie VS coaphton_serv") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make _run-coap-mini-interop-aiocoap-cli-vs-coapthon-server
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
                }
            }
            gitlabCommitStatus("EXECUTE mini-plugtest: aiocoap_clie VS coapthon_server") {
                long timeoutInSeconds = 600
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh '''
                            echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                            python3 -m pytest -s -p no:cacheprovider tests/integration_test__full_coap_interop_session.py -v
                        '''
                    }
                }
                catch (e){
                    sh '''
                        echo Do you smell the smoke in the room??
                        echo docker container logs :
                        sudo make get-logs
                    '''
                    throw e
                }
                finally {
                    sh '''
                        sudo -E make stop-all
                        sudo -E docker ps
                    '''
                }
            }
        }

        stage("RUN mini-plugtest: coapthon_clie VS californium_serv"){
            gitlabCommitStatus("START resources for mini-plugtest: coapthon_clie VS californium_serv") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make _run-coap-mini-interop-coapthon-cli-vs-californium-server
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
                }
            }
            gitlabCommitStatus("EXECUTE mini-plugtest: coapthon_clie VS californium_serv") {
                long timeoutInSeconds = 600
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh '''
                            echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                            python3 -m pytest -s -p no:cacheprovider tests/integration_test__full_coap_interop_session.py -v
                        '''
                    }
                }
                catch (e){
                    sh '''
                        echo Do you smell the smoke in the room??
                        echo docker container logs :
                        sudo make get-logs
                    '''
                    throw e
                }
                finally {
                    sh '''
                        sudo -E make stop-all
                        sudo -E docker ps
                    '''
                }
            }
        }

        stage("RUN mini-plugtest: californium_clie VS californium_serv"){
            gitlabCommitStatus("START resources for mini-plugtest: californium_clie VS californium_serv") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make _run-coap-mini-interop-californium-cli-vs-californium-server
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
                }
            }
            gitlabCommitStatus("EXECUTE mini-plugtest: californium_clie VS californium_serv") {
                long timeoutInSeconds = 600
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh '''
                            echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                            python3 -m pytest -s -p no:cacheprovider tests/integration_test__full_coap_interop_session.py -v
                        '''
                    }
                }
                catch (e){
                    sh '''
                        echo Do you smell the smoke in the room??
                        echo docker container logs :
                        sudo make get-logs
                    '''
                    throw e
                }
                finally {
                    sh '''
                        sudo -E make stop-all
                        sudo -E docker ps
                    '''
                }
            }

        }

        stage("RUN mini-plugtest: californium_clie VS coapthon_serv"){
            gitlabCommitStatus("START resources for mini-plugtest: californium_clie VS coapthon_serv") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make _run-coap-mini-interop-californium-cli-vs-coapthon-server
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
                }
            }
            gitlabCommitStatus("EXECUTE mini-plugtest: californium_clie VS coapthon_serv") {
                long timeoutInSeconds = 600
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh '''
                            echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                            python3 -m pytest -s -p no:cacheprovider tests/integration_test__full_coap_interop_session.py -v
                        '''
                    }
                }
                catch (e){
                    sh '''
                        echo Do you smell the smoke in the room??
                        echo docker container logs :
                        sudo make get-logs
                    '''
                    throw e
                }
                finally {
                    sh '''
                        sudo -E make stop-all
                        sudo -E docker ps
                    '''
                }
            }

        }

        stage("RUN mini-plugtest: coapthon_clie VS coapthon_serv"){
            gitlabCommitStatus("START resources for mini-plugtest: coapthon_clie VS coapthon_serv") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make _run-coap-mini-interop-coapthon-cli-vs-coapthon-server
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
                }
            }
            gitlabCommitStatus("EXECUTE mini-plugtest: coapthon_clie VS coapthon_serv") {
                long timeoutInSeconds = 600
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh '''
                            echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                            python3 -m pytest -s -p no:cacheprovider tests/integration_test__full_coap_interop_session.py -v
                        '''
                    }
                }
                catch (e){
                    sh '''
                        echo Do you smell the smoke in the room??
                        echo docker container logs :
                        sudo make get-logs
                    '''
                    throw e
                }
                finally {
                    sh '''
                        sudo -E make stop-all
                        sudo -E docker ps
                    '''
                }
            }
        }
    }
}



if(env.JOB_NAME =~ 'ioppytest-build-and-run-all-testing-tools/'){
    node('docker'){
        /* attention, here we use external RMQ server, else we would need to allow docker containers to access localhost's ports (docker host ports) */
        /* TODO use a deficated VHOST for these tests */
        env.AMQP_URL="amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/session02"
        env.AMQP_EXCHANGE="amq.topic"
        env.DOCKER_CLIENT_TIMEOUT=3000
        env.COMPOSE_HTTP_TIMEOUT=3000

        stage("Clone repo and submodules"){
            checkout scm
            sh '''
                git submodule update --init
                # tree .
            '''
        }

        stage("Install python dependencies"){
            gitlabCommitStatus("Install python dependencies"){
                withEnv(["DEBIAN_FRONTEND=noninteractive"]){
                    sh '''
                        sudo apt-get clean
                        sudo apt-get update
                        sudo apt-get upgrade -y -qq
                        sudo apt-get install --fix-missing -y -qq build-essential
                        sudo apt-get install --fix-missing -y -qq libyaml-dev
                        sudo apt-get install --fix-missing -y -qq libssl-dev openssl
                        sudo apt-get install --fix-missing -y -qq libffi-dev
                        sudo apt-get install --fix-missing -y -qq make
                    '''
                }
            }
        }

        stage("BUILD CoAP docker images (testing tools and automated-iuts)"){
            gitlabCommitStatus("BUILD CoAP docker images (testing tools and automated-iuts)") {
                sh '''
                    sudo -E make _docker-build-coap
                    sudo -E make _docker-build-coap-additional-resources
                    sudo -E docker images
                '''
            }
        }

        stage("BUILD OneM2M docker images (testing tools and automated-iuts)"){
            gitlabCommitStatus("BUILD OneM2M docker images (testing tools and automated-iuts)") {
                sh '''
                    sudo -E make _docker-build-onem2m
                    sudo -E make _docker-build-onem2m-additional-resources
                    sudo -E docker images
                '''
            }
        }

        stage("BUILD 6LoWPAN docker images (testing tools and automated-iuts)"){
            gitlabCommitStatus("BUILD 6LoWPAN docker images (testing tools and automated-iuts)") {
                sh '''
                    sudo -E make _docker-build-6lowpan
                    sudo -E make _docker-build-6lowpan-additional-resources
                    sudo -E docker images
                '''
            }
        }

        stage("BUILD CoMI docker images (testing tools and automated-iuts)"){
            gitlabCommitStatus("CoMI CoAP docker images (testing tools and automated-iuts)") {
                sh '''
                    sudo -E make _docker-build-comi
                    sudo -E make _docker-build-comi-additional-resources
                    sudo -E docker images
                '''
            }
        }

        stage("RUN CoAP testing tool container"){
            gitlabCommitStatus("RUN CoAP testing tool ") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make run-coap-testing-tool
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
                }
            }
         }

        stage("RUN OneM2M testing tool container"){
            gitlabCommitStatus("RUN OneM2M testing tool ") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make run-onem2m-testing-tool
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
                }
            }
        }

        stage("RUN CoMI testing tool container"){
            gitlabCommitStatus("RUN CoMI testing tool ") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make run-comi-testing-tool
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
                }
            }
        }

        stage("RUN 6LoWPAN testing tool container"){
            gitlabCommitStatus("RUN 6LoWPAN testing tool ") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 120

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make run-6lowpan-testing-tool
                            '''
                        }

                    } catch (err) {
                        long timePassed = System.currentTimeMillis() - startTime
                        if (timePassed >= timeoutInSeconds * 1000) {
                            echo 'Docker container kept on running!'
                            currentBuild.result = 'SUCCESS'
                        } else {
                            currentBuild.result = 'FAILURE'
                        }
                    }
                }
            }
        }
    }
}
