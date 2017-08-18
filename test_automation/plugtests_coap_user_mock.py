
from automated_IUTs.automation import UserEmulator
import pika, logging
from coap_testing_tool import AMQP_EXCHANGE, AMQP_URL




if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    u = UserEmulator(connection, 'coap_client')
    u.start()
    #INTERACTIVE_SESSION = False
    #logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

    #if INTERACTIVE_SESSION:
    #    logging.info(' shutting down, as INTERACTIVE MODE selected')
    #else:

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
        # server.supervisor.startProcess("automated_iut-coap_server-coapthon-v0.1", True)
        # server.supervisor.stopAllProcesses()

        # server.supervisor.startProcessGroup("client_coapthon_vs_server_coapthon", True)
        # server.supervisor.startProcessGroup("client_coapthon_vs_server_californium", True)
        # server.supervisor.startProcessGroup("client_californium_vs_server_coapthon", True)
        # server.supervisor.startProcessGroup("client_californium_vs_server_californium", True)
