import os
import argparse
import sys
import supervisor.xmlrpc
import xmlrpclib
import yaml
from jinja2 import Environment, FileSystemLoader
from coap_testing_tool import AMQP_URL

PATH = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_ENVIRONMENT = Environment(
    autoescape=False,
    loader=FileSystemLoader(os.path.join(PATH, 'templates')),
    trim_blocks=False)


def render_template(template_filename, context):
    return TEMPLATE_ENVIRONMENT.get_template(template_filename).render(context)


def create_plugtest_supervisor_conf(group_name, amqp_exchange,
                                    docker_client_name, docker_server_name, stdout_logfile_client,
                                    stdout_logfile_server, stderr_logfile_client, stderr_logfile_server,
                                    docker_testing_tool_name):
    if (group_name == 'plugtest1'):
        file_name = "conf.d/plugtest1.conf"
        prog_in_group = docker_client_name+", "+docker_server_name+", "+docker_testing_tool_name+", user_mock"
        program_variable = [
            [docker_client_name, stdout_logfile_client, stderr_logfile_client],
            [docker_server_name, stdout_logfile_server, stderr_logfile_server]]

    elif (group_name == 'plugtest2'):
        file_name = "conf.d/plugtest2.conf"
        prog_in_group = docker_client_name + ", " + docker_server_name + ", " + docker_testing_tool_name + ", user_mock"
        program_variable = [
            [docker_client_name, stdout_logfile_client, stderr_logfile_client],
            [docker_server_name, stdout_logfile_server, stderr_logfile_server]]

    elif (group_name == 'plugtest3'):
        file_name = "conf.d/plugtest3.conf"
        prog_in_group = docker_client_name + ", " + docker_server_name + ", " + docker_testing_tool_name + ", user_mock"
        program_variable = [
            [docker_client_name, stdout_logfile_client, stderr_logfile_client],
            [docker_server_name, stdout_logfile_server, stderr_logfile_server]]

    elif (group_name == 'plugtest4'):
        file_name = "conf.d/plugtest4.conf"
        prog_in_group = docker_client_name + ", " + docker_server_name + ", " + docker_testing_tool_name + ", user_mock"
        program_variable = [
            [docker_client_name, stdout_logfile_client, stderr_logfile_client],
            [docker_server_name, stdout_logfile_server, stderr_logfile_server]]

    else:
        program_variable = ''

    context = {
        'group_name': group_name,
        'amqp_exchange': amqp_exchange,
        'prog_in_group': prog_in_group,
        'program_variable': program_variable,
        'docker_testing_tool_name': docker_testing_tool_name,
        'amqp_url': AMQP_URL,
    }

    with open(file_name, 'w') as new_file:
        code = render_template('template_jinja.conf', context)
        new_file.write(code)

    return file_name


if __name__ == "__main__":
    # take in argument the name of client and server we want to use
    execute_plugtests = False
    testing_tool = False
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("-p", "--plugtest",
                            help="Give the name of the plugtest you want to execute (plugtest1, plugtest2, plugtest3, plugtest4)")
        parser.add_argument("--execute_plugtests", help="Execute all the four plugtest with supervisor",
                            action="store_true")
        parser.add_argument("--testing_tool", help="Execute the testing_tool with supervisor", action="store_true")
        args = parser.parse_args()
        if args.plugtest:
            group_name = args.plugtest
            if group_name != 'plugtest1' and group_name != 'plugtest2' and group_name != 'plugtest3' and group_name != 'plugtest4':
                raise Exception
        elif args.execute_plugtests:
            execute_plugtests = args.execute_plugtests
        elif args.testing_tool:
            testing_tool = args.testing_tool
        else:
            raise Exception

    except:
        print("ERROR, please see help (-h)")
        sys.exit(1)

    yamlfile = "test_automation/plugtests.conf.yaml"
    td_list = []
    with open(yamlfile, "r") as stream:
        yaml_docs = yaml.load_all(stream)
        for yaml_doc in yaml_docs:
            td_list.append(yaml_doc)

    if execute_plugtests == True:
        i = 1
        while i <= 4:
            group_name = "plugtest" + str(i)
            amqp_exchange = td_list[0].get(group_name)[0].get("amqp_exchange")
            docker_client_name = td_list[0].get(group_name)[1].get("docker_client_name")
            docker_server_name = td_list[0].get(group_name)[2].get("docker_server_name")
            stdout_logfile_client = td_list[0].get(group_name)[3].get("stdout_logfile_client")
            stdout_logfile_server = td_list[0].get(group_name)[4].get("stdout_logfile_server")
            stderr_logfile_client = td_list[0].get(group_name)[5].get("stderr_logfile_client")
            stderr_logfile_server = td_list[0].get(group_name)[6].get("stderr_logfile_server")
            docker_testing_tool_name = td_list[0].get(group_name)[7].get("docker_testing_tool_name")
            coap_client_ip = td_list[0].get(group_name)[8].get("coap_client_ip")
            coap_server_ip = td_list[0].get(group_name)[9].get("coap_server_ip")
            coap_server_port = td_list[0].get(group_name)[10].get("coap_server_port")

            file_name = create_plugtest_supervisor_conf(group_name, amqp_exchange,
                                                        docker_client_name, docker_server_name, stdout_logfile_client,
                                                        stdout_logfile_server, stderr_logfile_client, stderr_logfile_server,
                                                        docker_testing_tool_name)
            i = i + 1
    elif testing_tool == True:
        print("NOT implemented for the moment")
        sys.exit(1)

    else:
        amqp_exchange = td_list[0].get(group_name)[0].get("amqp_exchange")
        docker_client_name = td_list[0].get(group_name)[1].get("docker_client_name")
        docker_server_name = td_list[0].get(group_name)[2].get("docker_server_name")
        stdout_logfile_client = td_list[0].get(group_name)[3].get("stdout_logfile_client")
        stdout_logfile_server = td_list[0].get(group_name)[4].get("stdout_logfile_server")
        stderr_logfile_client = td_list[0].get(group_name)[5].get("stderr_logfile_client")
        stderr_logfile_server = td_list[0].get(group_name)[6].get("stderr_logfile_server")
        docker_testing_tool_name = td_list[0].get(group_name)[7].get("docker_testing_tool_name")
        coap_client_ip = td_list[0].get(group_name)[8].get("coap_client_ip")
        coap_server_ip = td_list[0].get(group_name)[9].get("coap_server_ip")
        coap_server_port = td_list[0].get(group_name)[10].get("coap_server_port")

        file_name = create_plugtest_supervisor_conf(group_name, amqp_exchange,
                                                    docker_client_name, docker_server_name, stdout_logfile_client,
                                                    stdout_logfile_server, stderr_logfile_client, stderr_logfile_server,
                                                    docker_testing_tool_name)

    socketpath = "/tmp/supervisor.sock"
    server = xmlrpclib.ServerProxy('http://127.0.0.1',
                                   transport=supervisor.xmlrpc.SupervisorTransport(
                                       None, None, serverurl='unix://' + socketpath))
    # launch supervisor
    print('doing this : sudo -E supervisord -c supervisor.conf')
    print(AMQP_URL)
    os.system('sudo -E supervisord -c supervisord.conf')
    # os.system('sudo supervisorctl -c supervisord.conf')

    # server.supervisor.startProcessGroup("plugtest1", True)

    print(server.supervisor.getState())
