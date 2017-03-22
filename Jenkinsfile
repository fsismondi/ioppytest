properties([[$class: 'GitLabConnectionProperty', gitLabConnection: 'figitlab']])

env.AMQP_URL="amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/jenkins_ci_session"

node('sudo'){
    stage ("Setup dependencies"){
    checkout([
        $class: 'GitSCM',
        branches: scm.branches,
        doGenerateSubmoduleConfigurations: true,
        extensions: scm.extensions + [[$class: 'SubmoduleOption', parentCredentials: true]],
        userRemoteConfigs: scm.userRemoteConfigs
    ])
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
        sudo pip install -r coap_testing_tool/agent/requirements.txt --upgrade
        sudo pip3 install -r coap_testing_tool/test_coordinator/requirements.txt --upgrade
        sudo pip3 install -r coap_testing_tool/test_analysis_tool/requirements.txt --upgrade
        sudo pip3 install -r coap_testing_tool/packet_router/requirements.txt --upgrade
        sudo pip3 install -r coap_testing_tool/sniffer/requirements.txt --upgrade
        sudo pip3 install -r coap_testing_tool/webserver/requirements.txt --upgrade
        '''
        }
    }
  }


  stage("Testing Tool components unit-testing"){
    gitlabCommitStatus("Testing Tool's components unit-testing"){
        sh "python3 -m pytest coap_testing_tool/test_coordinator/tests/tests.py"
    }
  }
}



