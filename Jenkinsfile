properties([[$class: 'GitLabConnectionProperty', gitLabConnection: 'figitlab']])

if(env.JOB_NAME =~ 'coap_testing_tool/'){
    node('sudo'){
        env.AMQP_URL="amqp://guest:guest@localhost/"
        env.AMQP_EXCHANGE="amq.topic"

        stage ("Setup dependencies"){
            checkout scm
            sh 'git submodule update --init'
            withEnv(["DEBIAN_FRONTEND=noninteractive"]){
                sh '''
                sudo apt-get clean
                sudo apt-get update
                sudo apt-get upgrade -y
                sudo apt-get install --fix-missing -y python-dev python-pip python-setuptools
                sudo apt-get install --fix-missing -y python3-dev python3-pip python3-setuptools
                sudo apt-get install --fix-missing -y build-essential
                sudo apt-get install --fix-missing -y libyaml-dev
                sudo apt-get install --fix-missing -y libssl-dev openssl
                sudo apt-get install --fix-missing -y libffi-dev
                sudo apt-get install --fix-missing -y curl tree netcat
                sudo apt-get install --fix-missing -y rabbitmq-server
                sudo rabbitmq-server -detached
                '''

            /* Show deployed code */
            sh "tree ."
          }
      }

      stage("Testing Tool components requirements"){
        gitlabCommitStatus("Testing Tool's components unit-testing"){
            withEnv(["DEBIAN_FRONTEND=noninteractive"]){
            sh '''
            sudo apt-get -y install supervisor
            sudo apt-get -y install tcpdump

            python3 -m pip install pytest --ignore-installed
            python3 -m pytest --version

            echo 'installing py2 dependencies'
            python -m pip install -r coap_testing_tool/agent/requirements.txt --upgrade

            echo 'installing py3 dependencies'
            python3 -m pip install -r coap_testing_tool/test_coordinator/requirements.txt --upgrade
            python3 -m pip install -r coap_testing_tool/test_analysis_tool/requirements.txt --upgrade
            python3 -m pip install -r coap_testing_tool/packet_router/requirements.txt --upgrade
            python3 -m pip install -r coap_testing_tool/sniffer/requirements.txt --upgrade
            python3 -m pip install -r coap_testing_tool/webserver/requirements.txt --upgrade
            '''
            }
        }
      }

      stage("unittesting submodules"){
        gitlabCommitStatus("Testing Tool's submodules unit-testing"){
            sh '''
            echo $AMQP_URL
            cd coap_testing_tool/test_analysis_tool
            pwd
            python3 -m pytest -p no:cacheprovider tests/test_core --ignore=tests/test_core/test_dissector/test_dissector_6lowpan.py
            '''
        }
      }

      stage("unittesting components"){
        gitlabCommitStatus("Testing Tool's components unit-testing"){
            sh '''
            echo $AMQP_URL
            echo $(which pytest)
            pwd
            python3 -m pytest -p no:cacheprovider coap_testing_tool/extended_test_descriptions/tests/tests.py
            python3 -m pytest -p no:cacheprovider coap_testing_tool/test_coordinator/tests/tests.py
            python3 -m pytest -p no:cacheprovider coap_testing_tool/packet_router/tests/tests.py
            '''
        }
      }

      stage("Testing Tool's AMQP API smoke tests"){

        gitlabCommitStatus("Testing Tool's AMQP API smoke tests"){
          try {
                sh '''
                echo 'AMQP PARAMS:'
                echo $AMQP_URL
                echo $AMQP_EXCHANGE
                sudo -E supervisorctl -c coap_testing_tool/supervisord.conf shutdown
                sleep 10
                sudo -E supervisord -c coap_testing_tool/supervisord.conf
                sleep 15
                sudo -E supervisorctl -c coap_testing_tool/supervisord.conf status
                sleep 2
                pwd
                python3 -m pytest -p no:cacheprovider tests/test_api.py -vv
                '''
          }
          catch (e){
            sh '''
            echo 'Do you smell the smoke in the room??'
            echo 'processes logs :'
            sudo -E supervisorctl -c coap_testing_tool/supervisord.conf tail -10000 tat
            sudo -E supervisorctl -c coap_testing_tool/supervisord.conf tail -10000 test-coordinator
            sudo -E supervisorctl -c coap_testing_tool/supervisord.conf tail -10000 agent
            sudo -E supervisorctl -c coap_testing_tool/supervisord.conf tail -10000 packet-router
            sudo -E supervisorctl -c coap_testing_tool/supervisord.conf tail -10000 packet-sniffer
            sudo -E supervisorctl -c coap_testing_tool/supervisord.conf tail -10000 bootstrap-agent-TT
            '''
            throw e
          }
          finally {
                sh '''
                sleep 5
                sudo -E supervisorctl -c coap_testing_tool/supervisord.conf status
                sleep 5
                sudo -E supervisorctl -c coap_testing_tool/supervisord.conf stop all
                '''
          }
        }
      }
    }
}


if(env.JOB_NAME =~ 'coap_testing_tool_ansible_playbook/'){
    node('sudo'){

        stage("Install Ansible"){
            sh '''
            sudo apt-get install --fix-missing -y  python-pip
            sudo apt-get install --fix-missing -y  ansible
            '''
        }

        stage("Build w/ Ansible Playbook"){
            checkout scm
            sh "git submodule update --init"
            sh "git submodule sync --recursive"
            gitlabCommitStatus("ansible-container") {
                sh "sudo ansible-playbook -i ansible/hosts.local ansible/main.yml --ask-become-pass"
            }
        }
    }
}

if(env.JOB_NAME =~ 'coap_testing_tool_ansible_container/'){

    node('docker'){
        env.DOCKER_CLIENT_TIMEOUT=3000
        env.COMPOSE_HTTP_TIMEOUT=3000

        stage("Build ansible-containers"){
            sh "sudo apt-get install -y python-pip"
            sh "sudo pip install ansible-container"
            checkout scm
            sh "git submodule update --init"
            sh "git submodule sync --recursive"
            sh "pwd"
            gitlabCommitStatus("ansible-container") {
                ansiColor('xterm'){
                    sh "sudo -E ansible-container --debug build"
                }
            }
        }
    }
}

if(env.JOB_NAME =~ 'coap_testing_tool_docker_build/'){
    node('docker'){

        env.AMQP_URL="amqp://guest:guest@localhost/"
        env.AMQP_EXCHANGE="amq.topic"
        env.DOCKER_CLIENT_TIMEOUT=3000
        env.COMPOSE_HTTP_TIMEOUT=3000
        env.TT_DOCKER_IMAGE_NAME="testing_tool-coap"

        stage("Clone repo and submodules"){
            checkout scm
            sh "git submodule update --init"
            sh "tree ."
        }

        stage("Creating CoAP testing tool docker image from Dockerfile"){
            gitlabCommitStatus("coap testing tool docker image") {

                sh "echo buiding coap_testing_tool docker image"
                sh "sudo -E docker build -t ${env.TT_DOCKER_IMAGE_NAME} ."
                sh "sudo -E docker images"
            }
        }

         stage("Testing Tool run"){
             long startTime = System.currentTimeMillis()
             long timeoutInSeconds = 30
             gitlabCommitStatus("Docker run") {
                sh "echo $AMQP_URL"
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh "sudo -E docker run -i --sig-proxy=true --env AMQP_EXCHANGE=$AMQP_EXCHANGE --env AMQP_URL=$AMQP_URL --privileged ${env.TT_DOCKER_IMAGE_NAME} "
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

if(env.JOB_NAME =~ 'coap_automated_iuts_docker_build_and_run/'){
    node('docker'){

        env.AMQP_URL="amqp://guest:guest@localhost/"
        env.AMQP_EXCHANGE="amq.topic"
        env.DOCKER_CLIENT_TIMEOUT=3000
        env.COMPOSE_HTTP_TIMEOUT=3000

        stage("Clone repo and submodules"){
            checkout scm
            sh "git submodule update --init"
            sh "tree ."
        }

        stage("automated_iut-coap_server-califronium: docker image BUILD"){
            env.AUTOMATED_IUT='coap_server_californium'

            gitlabCommitStatus("automated_iut-coap_server-califronium: docker image BUILD") {

                sh "echo buiding $AUTOMATED_IUT"
                sh "sudo -E docker build -t ${env.AUTOMATED_IUT} -f automated_IUTs/${env.AUTOMATED_IUT}/Dockerfile ."
                sh "sudo -E docker images"
            }
        }

         stage("automated_iut-coap_server-califronium: docker image RUN"){

            gitlabCommitStatus("automated_iut-coap_server-califronium: docker image RUN") {
                long startTime = System.currentTimeMillis()
                long timeoutInSeconds = 30
                gitlabCommitStatus("Docker run") {
                    sh "echo $AUTOMATED_IUT"
                    sh "echo $AMQP_URL"
                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh "sudo -E docker run -i --sig-proxy=true --env AMQP_EXCHANGE=$AMQP_EXCHANGE --env AMQP_URL=$AMQP_URL --privileged ${env.AUTOMATED_IUT} "
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

         stage("automated_iut-coap_client-coapthon: docker image BUILD"){
            gitlabCommitStatus("automated_iut-coap_client-coapthon: docker image BUILD") {
                env.AUTOMATED_IUT='coap_client_coapthon'

                sh "echo buiding $AUTOMATED_IUT"
                sh "sudo -E docker build -t ${env.AUTOMATED_IUT} -f automated_IUTs/${env.AUTOMATED_IUT}/Dockerfile ."
                sh "sudo -E docker images"
            }
        }

         stage("automated_iut-coap_client-coapthon: docker image RUN"){

            gitlabCommitStatus("automated_iut-coap_client-coapthon:: docker image RUN") {
                long startTime = System.currentTimeMillis()
                long timeoutInSeconds = 30
                gitlabCommitStatus("Docker run") {
                    sh "echo $AUTOMATED_IUT"
                    sh "echo $AMQP_URL"
                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh "sudo -E docker run -i --sig-proxy=true --env AMQP_EXCHANGE=$AMQP_EXCHANGE --env AMQP_URL=$AMQP_URL --privileged ${env.AUTOMATED_IUT} "
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


if(env.JOB_NAME =~ 'full_coap_interop_session/'){
    node('docker'){

        env.AMQP_URL="amqp://guest:guest@localhost/"
        env.AMQP_EXCHANGE="amq.topic"
        env.DOCKER_CLIENT_TIMEOUT=3000
        env.COMPOSE_HTTP_TIMEOUT=3000

        stage("Clone repo and submodules"){
            checkout scm
            sh "git submodule update --init"
            sh "tree ."
        }

        stage("Testing Tool components requirements"){
            gitlabCommitStatus("Testing Tool's components unit-testing"){
                withEnv(["DEBIAN_FRONTEND=noninteractive"]){
                    sh '''
                        sudo apt-get clean
                        sudo apt-get update
                        sudo apt-get upgrade -y
                        sudo apt-get install --fix-missing -y python-dev python-pip python-setuptools
                        sudo apt-get install --fix-missing -y python3-dev python3-pip python3-setuptools
                        sudo apt-get install --fix-missing -y build-essential
                        sudo apt-get install --fix-missing -y libyaml-dev
                        sudo apt-get install --fix-missing -y libssl-dev openssl
                        sudo apt-get install --fix-missing -y libffi-dev

                        python3 -m pip install pytest --ignore-installed
                        python3 -m pytest --version

                        echo 'installing py2 dependencies'
                        make install-requirements
                    '''
                }
            }
        }

        stage("docker BUILD testing tool and automated-iuts"){
            gitlabCommitStatus("docker BUILD testing tool and automated-iuts") {
                sh "sudo apt-get install --reinstall make"
                sh "sudo -E make docker-build-all "
                sh "sudo -E docker images"
            }
        }

        stage("docker RUN testing tool and automated-iuts"){
            gitlabCommitStatus("docker RUN testing tool and automated-iuts") {
                gitlabCommitStatus("Docker run") {
                    long startTime = System.currentTimeMillis()
                    long timeoutInSeconds = 45

                    sh "echo $AMQP_URL"

                    try {
                        timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                            sh "sudo -E make run-coap-client"
                            sh "sudo -E make run-coap-server"
                            sh "sudo -E make run-coap-testing-tool"
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

         stage("full_coap_interop_session"){
            gitlabCommitStatus("full_coap_interop_session") {
                long timeoutInSeconds = 600
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh '''
                            echo 'AMQP PARAMS:'
                            echo $AMQP_URL
                            echo $AMQP_EXCHANGE
                            python3 -m pytest -p no:cacheprovider tests/test_full_coap_interop_session.py -vvv
                        '''
                    }
                }
                catch (e){
                    sh '''
                        echo 'Do you smell the smoke in the room??'
                        echo 'docker container logs :'
                        sudo make get-logs
                    '''
                    throw e
                }
                finally {
                    sh '''
                        sudo make stop-all
                        sudo -E docker ps
                    '''
                }
            }

         }
    }
}