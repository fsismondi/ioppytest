properties([[$class: 'GitLabConnectionProperty', gitLabConnection: 'figitlab']])

if(env.JOB_NAME =~ 'coap_testing_tool/'){
    node('sudo'){
        env.AMQP_URL="amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/jenkins.coap_testing_tool"
        env.AMQP_EXCHANGE="default"

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
            sudo -H pip install pytest --ignore-installed
            sudo -H pip3 install pytest --ignore-installed
            sudo -H pip install -r coap_testing_tool/agent/requirements.txt --upgrade
            sudo -H pip3 install -r coap_testing_tool/test_coordinator/requirements.txt --upgrade
            sudo -H pip3 install -r coap_testing_tool/test_analysis_tool/requirements.txt --upgrade
            sudo -H pip3 install -r coap_testing_tool/packet_router/requirements.txt --upgrade
            sudo -H pip3 install -r coap_testing_tool/sniffer/requirements.txt --upgrade
            sudo -H pip3 install -r coap_testing_tool/webserver/requirements.txt --upgrade
            '''
            }
        }
      }


      stage("unittesting components"){
        gitlabCommitStatus("Testing Tool's components unit-testing"){
            sh '''
            echo $AMQP_URL
            pwd
            python3 -m pytest coap_testing_tool/test_coordinator/tests/tests.py
            python3 -m pytest coap_testing_tool/packet_router/tests/tests.py
            python3 -m pytest coap_testing_tool/extended_test_descriptions/tests/tests.py
            '''
        }
      }

        stage("unittesting submodules"){
        gitlabCommitStatus("Testing Tool's components unit-testing"){
            sh '''
            echo $AMQP_URL
            cd coap_testing_tool/test_analysis_tool
            pwd
            python3 -m pytest tests/test_core --ignore=tests/test_core/test_dissector/test_dissector_6lowpan.py
            '''
        }
      }

      stage("Functional API smoke tests"){
        gitlabCommitStatus("Functional API smoke tests"){
            sh '''
            echo $AMQP_URL
            sudo -E supervisord -c supervisor.conf
            sleep 15
            pwd
            python3 -m pytest tests/test_api.py -vv
            sleep 5
            sudo -E supervisorctl -c supervisor.conf stop all
            '''
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

        env.AMQP_URL = "amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/jenkins.coap_testing_tool_docker_build"
        env.AMQP_EXCHANGE="default"
        env.DIR='${env.JOB_NAME}_${env.BUILD_ID}'
        env.DOCKER_CLIENT_TIMEOUT=3000
        env.COMPOSE_HTTP_TIMEOUT=3000

        stage("Clone repo and submodules"){
            checkout scm
            sh "git submodule update --init"
            sh "tree ."
        }

        stage("Creating CoAP testing tool docker image from Dockerfile"){
            gitlabCommitStatus("coap testing tool docker image") {

                sh "echo $BUILD_ID"
                sh "echo cloning.."
                sh "git clone --recursive https://gitlab.f-interop.eu/fsismondi/coap_testing_tool.git ${env.DIR}"
                sh "echo buiding.."
                sh "sudo docker build -t finterop-coap ${env.DIR}"
                sh "sudo docker images"
            }
        }

         stage("Testing Tool run"){
             long startTime = System.currentTimeMillis()
             long timeoutInSeconds = 30
             gitlabCommitStatus("Docker run") {
                sh "echo $AMQP_URL"
                try {
                    timeout(time: timeoutInSeconds, unit: 'SECONDS') {
                        sh "sudo -E docker run -i --sig-proxy=true --env AMQP_EXCHANGE=$AMQP_EXCHANGE --env AMQP_URL=$AMQP_URL --privileged finterop-coap supervisord --nodaemon --configuration supervisor.conf"
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

        env.AMQP_URL = "amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/jenkins.coap_automated_iuts"
        env.AMQP_EXCHANGE="default"
        env.DOCKER_CLIENT_TIMEOUT=3000
        env.COMPOSE_HTTP_TIMEOUT=3000
        env.DIR='${env.JOB_NAME}_${env.BUILD_ID}'

        stage("Clone repo and submodules"){
            checkout scm
            sh "git submodule update --init"
            sh "tree ."
        }

        stage("automated_iut-coap_server-califronium: docker image BUILD"){
            gitlabCommitStatus("automated_iut-coap_server-califronium: docker image BUILD") {

                env.AUTOMATED_IUT='coap_server_californium'

                sh "echo $BUILD_ID"
                sh "echo $AUTOMATED_IUT"
                sh "echo cloning.."
                sh "git clone --recursive https://gitlab.f-interop.eu/fsismondi/coap_testing_tool.git ${env.DIR}"
                sh "cd ${env.DIR}"
                sh "echo buiding.."
                sh "sudo docker build -t ${env.AUTOMATED_IUT} -f automated_IUTs/${env.AUTOMATED_IUT}/Dockerfile ."
                sh "sudo docker images"
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

                sh "echo $BUILD_ID"
                sh "echo $AUTOMATED_IUT"
                sh "echo cloning.."
                sh "git clone --recursive https://gitlab.f-interop.eu/fsismondi/coap_testing_tool.git ${env.DIR}"
                sh "cd ${env.DIR}"
                sh "echo buiding.."
                sh "sudo docker build -t ${env.AUTOMATED_IUT} -f automated_IUTs/${env.AUTOMATED_IUT}/Dockerfile ."
                sh "sudo docker images"
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