import os
import argparse
import sys
import supervisor.xmlrpc
import xmlrpclib
import yaml
from jinja2 import Environment, FileSystemLoader

PATH = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_ENVIRONMENT = Environment(
    autoescape=False,
    loader=FileSystemLoader(os.path.join(PATH, 'templates')),
    trim_blocks=False)

def render_template(template_filename, context):
    return TEMPLATE_ENVIRONMENT.get_template(template_filename).render(context)


def create_plugtest_supervisor_conf(group_name, amqp_exchange, server_name, client_name):

    if (group_name == 'plugtest1') :
        file_name = "conf.d/plugtest1.conf"
        groupe_name = "plugtest1"
        prog_in_group = "automated_iut-coap_client-californium-v0.1, automated_iut-coap_server-californium-v0.1, testing_tool-interoperability-coap-v-0.5, user_mock"
        program_variable = [
            ['automated_iut-coap_client-californium-v0.1', 'automated_iut-coap_client-californium-v0.1-stdout.log',
             'automated_iut-coap_client-californium-v0.1-stderr.log', 'amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/plugtests_01'],
            ['automated_iut-coap_server-californium-v0.1', 'automated_iut-coap_server-californium-v0.1-stdout.log',
             'automated_iut-coap_server-californium-v0.1-stderr.log', 'amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/plugtests_01']]

    elif (group_name == 'plugtest2') :
        file_name = "conf.d/plugtest2.conf"
        groupe_name = "plugtest2"
        prog_in_group = "automated_iut-coap_server-californium-v0.1, automated_iut-coap_client-coapthon-v0.1, testing_tool-interoperability-coap-v-0.5, user_mock"
        program_variable = [
            ['automated_iut-coap_server-californium-v0.1', 'automated_iut-coap_server-californium-v0.1-stdout.log',
             'automated_iut-coap_server-californium-v0.1-stderr.log', 'amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/plugtests_02'],
            ['automated_iut-coap_client-coapthon-v0.1', 'automated_iut-coap_client-coapthon-v0.1-stdout.log',
             'automated_iut-coap_client-coapthon-v0.1-stderr.log', 'amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/plugtests_02']]

    elif (group_name == 'plugtest3'):
        file_name = "conf.d/plugtest3.conf"
        groupe_name = "plugtest3"
        prog_in_group = "automated_iut-coap_client-coapthon-v0.1, automated_iut-coap_server-coapthon-v0.1, testing_tool-interoperability-coap-v-0.5, user_mock"
        program_variable = [
            ['automated_iut-coap_client-coapthon-v0.1', 'automated_iut-coap_client-coapthon-v0.1-stdout.log',
             'automated_iut-coap_client-coapthon-v0.1-stderr.log', 'amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/plugtests_03'],
            ['automated_iut-coap_server-coapthon-v0.1', 'automated_iut-coap_server-coapthon-v0.1-stdout.log',
             'automated_iut-coap_server-coapthon-v0.1-stderr.log', 'amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/plugtests_03']]

    elif (group_name == 'plugtest4'):
        file_name = "conf.d/plugtest4.conf"
        groupe_name = "plugtest4"
        prog_in_group = "automated_iut-coap_client-californium-v0.1, automated_iut-coap_server-coapthon-v0.1, testing_tool-interoperability-coap-v-0.5, user_mock"
        program_variable = [
            ['automated_iut-coap_client-californium-v0.1', 'automated_iut-coap_client-californium-v0.1-stdout.log',
             'automated_iut-coap_client-californium-v0.1-stderr.log', 'amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/plugtests_04'],
            ['automated_iut-coap_server-coapthon-v0.1', 'automated_iut-coap_server-coapthon-v0.1-stdout.log',
             'automated_iut-coap_server-coapthon-v0.1-stderr.log', 'amqp://paul:iamthewalrus@f-interop.rennes.inria.fr/plugtests_04']]

    else :
        program_variable = ''

    context = {
        'groupe_name': groupe_name,
        'prog_in_group': prog_in_group,
        'program_variable': program_variable,
        'amqp_exchange': amqp_exchange,

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
        parser.add_argument("-p","--plugtest", help="increase output verbosity")
        parser.add_argument("--execute_plugtests", help="increase output verbosity", action="store_true")
        parser.add_argument("--testing_tool", help="increase output verbosity", action="store_true")
        args = parser.parse_args()
        if args.plugtest:
            group_name = args.plugtest
        elif args.execute_plugtests:
            execute_plugtests = args.execute_plugtests
        elif args.testing_tool:
            testing_tool = args.testing_tool
        else :
            raise Exception

    except:
        print("Error, please see help (-h)")
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
            amqp_exchange = td_list[0].get("plugtest"+str(i))[0].get("amqp_exchange")
            client_name = td_list[0].get("plugtest"+str(i))[1].get("coap_client")
            server_name = td_list[0].get("plugtest"+str(i))[2].get("coap_server")
            group_name = "plugtest"+str(i)
            file_name = create_plugtest_supervisor_conf(group_name, amqp_exchange, server_name, client_name)
            i = i + 1
    elif testing_tool == True:
        print("NOT implemented for the moment")
        sys.exit(1)

    else :
        if group_name == "plugtest1":
            i = 1
        elif group_name == "plugtest2":
            i = 2
        elif group_name == "plugtest3":
            i = 3
        elif group_name == "plugtest4":
            i = 4

        amqp_exchange = td_list[0].get("plugtest" + str(i))[0].get("amqp_exchange")
        client_name = td_list[0].get("plugtest" + str(i))[1].get("coap_client")
        server_name = td_list[0].get("plugtest" + str(i))[2].get("coap_server")
        group_name = "plugtest" + str(i)
        file_name = create_plugtest_supervisor_conf(group_name, amqp_exchange, server_name, client_name)

    socketpath = "/tmp/supervisor.sock"
    server = xmlrpclib.ServerProxy('http://127.0.0.1',
                                   transport=supervisor.xmlrpc.SupervisorTransport(
                                       None, None, serverurl='unix://' + socketpath))
    #launch supervisor
    print('doing this : sudo -E supervisord -c supervisor.conf')
    os.system('sudo -E supervisord -c supervisord.conf')
    #os.system('sudo supervisorctl -c supervisord.conf')

    #server.supervisor.startProcessGroup("plugtest1", True)

    print(server.supervisor.getState())

