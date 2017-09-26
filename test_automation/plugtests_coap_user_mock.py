import os
import pika
import logging
import webbrowser

from automated_IUTs.automation import UserMock
from coap_testing_tool import AMQP_EXCHANGE, AMQP_URL
from coap_testing_tool.webserver.webserver import create_html_test_results, FILENAME_HTML_REPORT


def open_test_results_with_browser():
    webbrowser.open('file://' + os.path.realpath(FILENAME_HTML_REPORT))


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

    # e.g. for TD COAP CORE from 1 to 31
    tc_list = ['TD_COAP_CORE_%02d_v01' % tc for tc in range(1, 31)]

    u = UserMock(connection, tc_list)
    u.start()
    u.join()

    #  finishing Session..
    create_html_test_results()
    open_test_results_with_browser()


    # INTERACTIVE_SESSION = False
    # logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

    # if INTERACTIVE_SESSION:
    #    logging.info(' shutting down, as INTERACTIVE MODE selected')
    # else:

    #    iut = UserEmulator("test", "test2")
    #    iut.start()
    #    iut.join()



    # socketpath = "/tmp/supervisor.sock"
    # server = xmlrpclib.ServerProxy('http://127.0.0.1',
    #                              transport=supervisor.xmlrpc.SupervisorTransport(
    #                                  None, None, serverurl='unix://' + socketpath))
    # print(server.supervisor.getState())
    # print(server.supervisor.readLog(0, 101))
    # print(server.supervisor.getProcessInfo("agent"))
    # print(server.supervisor.getProcessInfo("tat"))
    # print(server.supervisor.getAllProcessInfo())
    # print(server.supervisor.restart())
    # server.supervisor.startProcess("automated_iut-coap_server-coapthon-v0.8", True)
    # server.supervisor.stopAllProcesses()

    # server.supervisor.startProcessGroup("client_coapthon_vs_server_coapthon", True)
    # server.supervisor.startProcessGroup("client_coapthon_vs_server_californium", True)
    # server.supervisor.startProcessGroup("client_californium_vs_server_coapthon", True)
    # server.supervisor.startProcessGroup("client_californium_vs_server_californium", True)
