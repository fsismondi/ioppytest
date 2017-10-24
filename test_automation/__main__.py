#!/usr/bin/env python2.7

import os
import argparse
import sys
import supervisor.xmlrpc
import logging
import time
import xmlrpclib
import yaml
import socket
import json
from jinja2 import Environment, FileSystemLoader
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE, INTERACTIVE_SESSION

PATH = os.path.dirname(os.path.abspath(__file__))
PLUGTESTS_CONFIG = "test_automation/plugtests.yaml"
SUPERVISORD_CONFIG_DIR = "conf.d"
SUPERVISORD_CONFIG_FILE = "supervisord.conf"  # parent conf file
USER_MOCK_SCRIPT_NAME = "user_mock"
TEMPLATE_ENVIRONMENT = Environment(
    autoescape=False,
    loader=FileSystemLoader(os.path.join(PATH, 'templates')),
    trim_blocks=False)


def render_template(template_filename, context):
    return TEMPLATE_ENVIRONMENT.get_template(template_filename).render(context)


def create_plugtest_supervisor_conf(group_name, amqp_exchange, amqp_url,
                                    docker_client_name, docker_server_name, stdout_logfile_client,
                                    stdout_logfile_server, stderr_logfile_client, stderr_logfile_server,
                                    docker_testing_tool_name):
    group_config_filename = os.path.join(SUPERVISORD_CONFIG_DIR, group_name + '.conf')
    prog_list_in_group = "{}, {}, {}, {}".format(docker_testing_tool_name, docker_client_name, docker_server_name,
                                                 USER_MOCK_SCRIPT_NAME)

    iuts_prog_config = [
        [docker_client_name, stdout_logfile_client, stderr_logfile_client],
        [docker_server_name, stdout_logfile_server, stderr_logfile_server]
    ]

    template_fields = {
        'group_name': group_name,
        'amqp_exchange': amqp_exchange,
        'amqp_url': amqp_url,
        'prog_list_in_group': prog_list_in_group,
        'iuts_prog_config': iuts_prog_config,
        'docker_testing_tool_name': docker_testing_tool_name,

    }

    with open(group_config_filename, 'w') as new_file:
        code = render_template('template_jinja.conf', template_fields)
        new_file.write(code)

    return group_config_filename


if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

    # remove old config files
    config_files = os.listdir(SUPERVISORD_CONFIG_DIR)
    for item in config_files:
        if item.endswith(".config"):
            print("removing config files: %s" % item)
            os.remove(os.path.join(SUPERVISORD_CONFIG_DIR, item))

    # load config from yaml
    with open(PLUGTESTS_CONFIG, "r") as stream:
        plugtests_config_dict = yaml.load(stream)

    choices = [plugest_item for plugest_item in plugtests_config_dict.keys()]

    option_execute_all = False
    option_testing_tool_only = False

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--plugtest",
                            help="Plugtest id you want to execute. Choices: %s. see %s for more details." % (
                            choices, PLUGTESTS_CONFIG),
                            type=str,

                            )

        parser.add_argument("--execute_all",
                            help="Execute all plugtests with supervisor, each process component as a docker container",
                            action="store_true")

        parser.add_argument("--testing_tool_only",
                            help="Execute only testing_tool (with supervisor)",
                            action="store_true")

        args = parser.parse_args()

        if args.plugtest:
            option_plugtest = args.plugtest
        elif args.execute_all:
            option_execute_all = args.execute_all
        elif args.testing_tool:
            option_testing_tool_only = args.testing_tool_only
        else:
            raise Exception

    except Exception as e:
        print("ERROR, please see help (-h)")
        print(e)
        sys.exit(1)

    td_list = []

    socketpath = "/tmp/supervisor.sock"
    server = xmlrpclib.ServerProxy('http://127.0.0.1',
                                   transport=supervisor.xmlrpc.SupervisorTransport(
                                       None, None,
                                       serverurl='unix://' + socketpath)
                                   )

    if option_execute_all:
        for plugtest_name, config in plugtests_config_dict.items():
            docker_client_name = config["docker_client_name"]
            docker_server_name = config["docker_server_name"]
            stdout_logfile_client = config["stdout_logfile_client"]
            stdout_logfile_server = config["stdout_logfile_server"]
            stderr_logfile_client = config["stderr_logfile_client"]
            stderr_logfile_server = config["stderr_logfile_server"]
            docker_testing_tool_name = config["docker_testing_tool_name"]
            coap_client_ip = config["coap_client_ip"]
            coap_server_ip = config["coap_server_ip"]
            coap_server_port = config["coap_server_port"]

            file_name = create_plugtest_supervisor_conf(plugtest_name,
                                                        AMQP_EXCHANGE,
                                                        AMQP_URL,
                                                        docker_client_name,
                                                        docker_server_name,
                                                        stdout_logfile_client,
                                                        stdout_logfile_server, stderr_logfile_client,
                                                        stderr_logfile_server,
                                                        docker_testing_tool_name)

    elif option_testing_tool_only is True:
        print("NOT implemented for the moment")
        sys.exit(1)

    elif option_plugtest:
        print("Executing: %s" % option_plugtest)
        config = plugtests_config_dict[option_plugtest]
        amqp_exchange = AMQP_EXCHANGE
        amqp_url = AMQP_URL
        docker_client_name = config["docker_client_name"]
        docker_server_name = config["docker_server_name"]
        stdout_logfile_client = config["stdout_logfile_client"]
        stdout_logfile_server = config["stdout_logfile_server"]
        stderr_logfile_client = config["stderr_logfile_client"]
        stderr_logfile_server = config["stderr_logfile_server"]
        docker_testing_tool_name = config["docker_testing_tool_name"]
        coap_client_ip = config["coap_client_ip"]
        coap_server_ip = config["coap_server_ip"]
        coap_server_port = config["coap_server_port"]

        file_name = create_plugtest_supervisor_conf(option_plugtest,
                                                    amqp_exchange,
                                                    amqp_url,
                                                    docker_client_name,
                                                    docker_server_name,
                                                    stdout_logfile_client,
                                                    stdout_logfile_server,
                                                    stderr_logfile_client,
                                                    stderr_logfile_server,
                                                    docker_testing_tool_name)

        try:
            server.supervisor.stopAllProcesses()
            logging.info(server.supervisor.getState())
            logging.info(server.supervisor.getAllProcessInfo())
            logging.info("Starting processes from config file: %s" % SUPERVISORD_CONFIG_FILE)
            server.supervisor.startProcessGroup(option_plugtest, True)
            time.sleep(2)
            logging.info(server.supervisor.getAllProcessInfo())

        except socket.error:
            os.system('sudo -E supervisord -c supervisord.conf')
            server.supervisor.stopAllProcesses()
            logging.info(server.supervisor.getState())
            logging.info(server.supervisor.getAllProcessInfo())
            logging.info("Starting processes from config file: %s" % SUPERVISORD_CONFIG_FILE)
            server.supervisor.startProcessGroup(option_plugtest, True)
            time.sleep(2)
            logging.info(server.supervisor.getAllProcessInfo())

    if option_execute_all:
        for plugtest_name, config in plugtests_config_dict.items():
            try:
                server.supervisor.stopAllProcesses()
                logging.info(server.supervisor.getState())
                logging.info(server.supervisor.getAllProcessInfo())
                logging.info("Starting processes from config file: %s" % SUPERVISORD_CONFIG_FILE)
                server.supervisor.startProcessGroup(plugtest_name, True)
                time.sleep(2)
                logging.info(server.supervisor.getAllProcessInfo())

            except socket.error:
                os.system('sudo -E supervisord -c supervisord.conf')
                server.supervisor.stopAllProcesses()
                logging.info(server.supervisor.getState())
                logging.info(server.supervisor.getAllProcessInfo())
                logging.info("Starting processes from config file: %s" % SUPERVISORD_CONFIG_FILE)
                server.supervisor.startProcessGroup(plugtest_name, True)
                time.sleep(2)
                logging.info(server.supervisor.getAllProcessInfo())

            # body_dict = json.loads(body.decode('utf-8'), object_pairs_hook=OrderedDict)
            # msg_type = body_dict['_type']
            #
            # while msg_type != 'testingtool.terminate':
            #     # MsgTestingToolTerminate
            #     wait()
            #








                # os.system('sudo supervisorctl -c supervisord.conf')

                # server.supervisor.startProcessGroup("plugtest1", True)
