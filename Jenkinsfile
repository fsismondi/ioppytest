properties([[$class: 'GitLabConnectionProperty', gitLabConnection: 'figitlab']])

if(env.JOB_NAME =~ 'ioppytest/'){
    node('sudo'){
        env.AMQP_URL="amqp://guest:guest@localhost/"
        env.AMQP_EXCHANGE="amq.topic"

        stage("Clone repo and submodules"){
            checkout scm
            sh '''
                git submodule update --init
                tree .
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

      stage("unittesting git submodules"){
        gitlabCommitStatus("unittesting git submodules"){
            sh '''
                echo $AMQP_URL
                make _test_submodules
            '''
        }
      }

      stage("unittesting components"){
        gitlabCommitStatus("unittesting components"){
            sh '''
                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                make tests
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
                    python3 -m pytest -p no:cacheprovider tests/test_api.py -v
                '''
          }
          catch (e){
            sh '''
                echo Do you smell the smoke in the room??
                echo processes logs :
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE tail -10000 tat
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE tail -10000 test-coordinator
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE tail -10000 agent
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE tail -10000 packet-router
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE tail -10000 packet-sniffer
                sudo -E supervisorctl -c $SUPERVISOR_CONFIG_FILE tail -10000 bootstrap-agent-TT
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


if(env.JOB_NAME =~ 'CoAP testing tool/'){
    node('docker'){

        /* attention, here we use external RMQ server, else we would need to allow docker containers to access localhost's ports (docker host ports) */
        env.AMQP_URL="amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/jenkins.full_coap_interop_session"
        env.AMQP_EXCHANGE="amq.topic"
        env.DOCKER_CLIENT_TIMEOUT=3000
        env.COMPOSE_HTTP_TIMEOUT=3000

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

        stage("BUILD CoAP docker images (testing tools and automated-iuts)"){
            gitlabCommitStatus("BUILD CoAP docker images (testing tools and automated-iuts)") {
                sh '''
                    sudo -E make _docker-build-coap
                    sudo -E make _docker-build-coap-additional-resources
                    sudo -E docker images
                '''
            }
        }

        stage("RUN CoAP containers for mini-plugtests"){
            gitlabCommitStatus("RUN CoAP containers for mini-plugtests") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 45

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh '''
                                echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                                sudo -E make run-coap-client
                                sudo -E make run-coap-server
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

        stage("EXECUTE CoAP mini-plugtests"){
            gitlabCommitStatus("EXECUTE CoAP mini-plugtests") {
                long timeoutInSeconds = 600
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh '''
                            echo AMQP params:  { url: $AMQP_URL , exchange: $AMQP_EXCHANGE}
                            python3 -m pytest -s -p no:cacheprovider tests/test_full_coap_interop_session.py -v
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
                        sudo -E make stop-coap-client
                        sudo -E make stop-coap-server
                        sudo -E make stop-coap-testing-tool
                        sudo -E docker ps
                    '''
                }
            }

        }
    }
}
