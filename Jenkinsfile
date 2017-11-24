properties([[$class: 'GitLabConnectionProperty', gitLabConnection: 'figitlab']])

if(env.JOB_NAME =~ 'ioppytest/'){
    node('sudo'){
        env.AMQP_URL="amqp://guest:guest@localhost/"
        env.AMQP_EXCHANGE="amq.topic"

        stage ("Environment dependencies"){
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
                echo 'restarting rmq server and app'
                sudo rabbitmq-server -detached || true
                sudo rabbitmqctl stop_app || true
                sudo rabbitmqctl start_app || true
                '''

            /* Show deployed code */
            sh "tree ."
          }
      }

      stage("Testing Tool dependencies"){
        gitlabCommitStatus("Testing Tool dependencies"){
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

      stage("unittesting git submodules"){
        gitlabCommitStatus("unittesting git submodules"){
            sh '''
            echo $AMQP_URL
            cd coap_testing_tool/test_analysis_tool
            pwd
            python3 -m pytest -p no:cacheprovider tests/test_core --ignore=tests/test_core/test_dissector/test_dissector_6lowpan.py
            '''
        }
      }

      stage("unittesting components"){
        gitlabCommitStatus("unittesting components"){
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

      stage("CoAP testing tool - AMQP API smoke tests"){
        gitlabCommitStatus("CoAP testing tool - AMQP API smoke tests"){
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