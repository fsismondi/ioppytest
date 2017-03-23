properties([[$class: 'GitLabConnectionProperty', gitLabConnection: 'figitlab']])

if(env.JOB_NAME =~ 'coap_testing_tool/'){
    node('sudo'){

        environment {
                AMQP_URL = "amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/ci."${JOB_NAME}
                AMQP_EXCHANGE="default"
            }

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
            sh "echo $AMQP_URL"
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


      stage("Testing Tool components unit-testing"){
        gitlabCommitStatus("Testing Tool's components unit-testing"){
            sh '''
            python3 -m pytest coap_testing_tool/test_coordinator/tests/tests.py
            python3 -m pytest coap_testing_tool/packet_router/tests/tests.py
            python3 -m pytest coap_testing_tool/extended_test_descriptions/tests/tests.py
            '''
        }
      }

        stage("Test submodules"){
        gitlabCommitStatus("Testing Tool's components unit-testing"){
            sh '''
            cd coap_testing_tool/test_analysis_tool
            sudo python3 -m pytest tests/test_core
            '''
        }
      }
    }
}


if(env.JOB_NAME =~ 'coap_testing_tool_docker_build/'){
    node('sudo'){
        stage ("Install docker"){
            withEnv(["DEBIAN_FRONTEND=noninteractive"]){
                sh '''
                sudo apt-get clean
                sudo apt-get update
                sudo apt-get upgrade -y
                sudo apt-get install --fix-missing -y curl tree netcat

                curl -sSL https://get.docker.com/ | sudo sh
                sudo service docker start
                '''

                /* Show deployed code */
                sh "tree ."
            }
        }

        stage("Clone repo and submodules"){
            checkout scm
            sh 'git submodule update --init'
            sh "tree ."
        }

        stage("Creating CoAP testing tool docker image from Dockerfile"){
            gitlabCommitStatus("coap testing tool docker image") {
                env.DOCKER_CLIENT_TIMEOUT=3000
                env.COMPOSE_HTTP_TIMEOUT=3000
                sh '''
                git clone --recursive https://gitlab.f-interop.eu/fsismondi/coap_testing_tool.git /tmp/coap_testing_tool_${BUILD_NUMBER}
                sudo docker build -t finterop-coap /tmp/coap_testing_tool_${BUILD_NUMBER}
                sudo docker images
                '''
            }
        }
    }
}


if(env.JOB_NAME =~ 'coap_testing_tool_ansible_playbook/'){
    node('sudo'){
        stage("Install w/ Ansible Playbook"){
            sh "sudo apt-get install -y python-pip"
            sh "sudo apt install ansible"
            checkout scm
            sh "git submodule update --init"
            sh "git submodule sync --recursive"
            sh "pwd"
            gitlabCommitStatus("ansible-container") {
                sh "sudo ansible-playbook -i ansible/hosts.local ansible/main.yml --ask-become-pass"
                }
            }
        }
    }
}

if(env.JOB_NAME =~ 'coap_testing_tool_ansible_container/'){
    node('sudo'){
        stage("Build ansible-containers"){
            sh "sudo apt-get install -y python-pip"
            sh "sudo pip install ansible-container"
            checkout scm
            sh "git submodule update --init"
            sh "git submodule sync --recursive"
            sh "pwd"
            gitlabCommitStatus("ansible-container") {
                env.DOCKER_CLIENT_TIMEOUT=3000
                env.COMPOSE_HTTP_TIMEOUT=3000
                ansiColor('xterm'){
                    sh "sudo ansible-container --debug build"
                }
            }
        }
    }
}
