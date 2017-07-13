import pika
import threading
import logging
import subprocess
import sys
import signal
from coap_testing_tool.utils.event_bus_messages import *
from coap_testing_tool.utils.amqp_synch_call import publish_message
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE, INTERACTIVE_SESSION

class UserEmulator(threading.Thread):
    """
    this class servers for moking user inputs into GUI
    """
    component_id = 'user_emulation'

    implemented_testcases_list = [
        'TD_COAP_CORE_01_v01',
        'TD_COAP_CORE_02_v01',
        'TD_COAP_CORE_03_v01',
        'TD_COAP_CORE_04_v01',
    ]

    def __init__(self, iut_testcases, iut_node):
        threading.Thread.__init__(self)
        self.message_count = 0
        # queues & default exchange declaration
        self.iut_node = iut_node
        self.iut_testcases = iut_testcases

        # lets create connection
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        self.channel = connection.channel()

        # in case exchange not not declared
        connection.channel().exchange_declare(exchange=AMQP_EXCHANGE,
                                              type='topic',
                                              durable=True,
                                              )

        services_queue_name = 'services_queue@%s' % self.component_id
        self.channel.queue_declare(queue=services_queue_name, auto_delete=True)
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=services_queue_name,
                                routing_key='control.testcoordination')
        publish_message(self.channel, MsgTestingToolComponentReady(component=self.component_id))
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.on_request, queue=services_queue_name)

    def stop(self):

        self.channel.stop_consuming()

    def on_request(self, ch, method, props, body):

        ch.basic_ack(delivery_tag=method.delivery_tag)

        props_dict = {
            'content_type': props.content_type,
            'delivery_mode': props.delivery_mode,
            'correlation_id': props.correlation_id,
            'reply_to': props.reply_to,
            'message_id': props.message_id,
            'timestamp': props.timestamp,
            'user_id': props.user_id,
            'app_id': props.app_id,
        }
        event = Message.from_json(body)
        event.update_properties(**props_dict)

        self.message_count += 1

        if event is None:
            return

        elif isinstance(event, MsgTestCaseReady):
            if event.testcase_id in self.implemented_testcases_list:
                m = MsgTestCaseStart()
                publish_message(self.channel, m)
                logging.info('Event received %s' % event._type)
                logging.info('Event pushed %s' % m)
            else:
                m = MsgTestCaseSkip(testcase_id=event.testcase_id)
                publish_message(self.channel, m)
                logging.info('Event received %s' % event._type)
                logging.info('Event pushed %s' % m)

        elif isinstance(event, MsgTestingToolReady):
            m = MsgTestSuiteStart()
            publish_message(self.channel, m)
            logging.info('Event received %s' % event._type)
            logging.info('Event pushed %s' % m)

        elif isinstance(event, MsgTestSuiteReport):
            logging.info('Test suite finished, final report: %s' % event.to_json())
            self._exit

        else:

            logging.info('Event received and ignored: %s' % event._type)

    def _exit(self):
        time.sleep(2)
        self.connection.close()
        sys.exit(0)

    def run(self):
        print("Starting thread listening on the event bus")
        self.channel.start_consuming()
        print('Bye byes!')


if __name__ == '__main__':
    INTERACTIVE_SESSION = False
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

    if INTERACTIVE_SESSION:
        logging.info(' shutting down, as INTERACTIVE MODE selected')
    else:

        iut = UserEmulator("test", "test2")
        iut.start()
        iut.join()


        #socketpath = "/tmp/supervisor.sock"
    #server = xmlrpclib.ServerProxy('http://127.0.0.1',
    #                              transport=supervisor.xmlrpc.SupervisorTransport(
    #                                  None, None, serverurl='unix://' + socketpath))
    #print(server.supervisor.getState())
    #print(server.supervisor.readLog(0, 101))
    #print(server.supervisor.getProcessInfo("agent"))
    #print(server.supervisor.getProcessInfo("tat"))
    #print(server.supervisor.getAllProcessInfo())
    #print(server.supervisor.restart())
    #server.supervisor.startProcess("automated_iut-coap_server-coapthon-v0.1", True)
    #server.supervisor.stopAllProcesses()

    #server.supervisor.startProcessGroup("client_coapthon_vs_server_coapthon", True)
    #server.supervisor.startProcessGroup("client_coapthon_vs_server_californium", True)
    #server.supervisor.startProcessGroup("client_californium_vs_server_coapthon", True)
    #server.supervisor.startProcessGroup("client_californium_vs_server_californium", True)
