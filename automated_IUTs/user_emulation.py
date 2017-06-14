# -*- coding: utf-8 -*-
# !/usr/bin/env python3
"""
Example of python code for implementing an automated IUT.
This is basically a component listening to the AMQP events, and wrapping the IUT in order to execute the right commands.
"""

import pika
import threading
import logging
import subprocess
import sys
import signal
from coap_testing_tool.utils.event_bus_messages import *
from coap_testing_tool.utils.amqp_synch_call import publish_message
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE, INTERACTIVE_SESSION

logger = logging.getLogger(__name__)

COMPONENT_ID = 'user_emulation'

# timeout in seconds
STIMULI_HANDLER_TOUT = 10

testcases_to_execute = [
    'TD_COAP_CORE_01_v01',
    'TD_COAP_CORE_02_v01',
    'TD_COAP_CORE_03_v01',
    'TD_COAP_CORE_04_v01',
]


def signal_int_handler(signal, frame):
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    channel = connection.channel()

    publish_message(
            channel,
            MsgTestingToolComponentShutdown(component=COMPONENT_ID)
    )

    logger.info('got SIGINT. Bye bye!')

    sys.exit(0)


signal.signal(signal.SIGINT, signal_int_handler)


class UserEmulator(threading.Thread):
    def __init__(self, conn):
        threading.Thread.__init__(self)
        self.message_count = 0
        # queues & default exchange declaration
        self.connection = conn
        self.channel = connection.channel()
        services_queue_name = 'services_queue@%s' % COMPONENT_ID
        self.channel.queue_declare(queue=services_queue_name, auto_delete=True)
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=services_queue_name,
                                routing_key='control.testcoordination')
        publish_message(self.channel, MsgTestingToolComponentReady(component=COMPONENT_ID))
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
            if event.testcase_id in testcases_to_execute:
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
            publish_message(self.channel, m )
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
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

    # lets create connection
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

    channel = connection.channel()

    # in case exchange not not declared
    connection.channel().exchange_declare(exchange=AMQP_EXCHANGE,
                                          type='topic',
                                          durable=True,
                                          )

    if INTERACTIVE_SESSION:
        logging.info('%s shutting down, as INTERACTIVE MODE selected' % COMPONENT_ID)
    else:
        iut = UserEmulator(connection)
        iut.start()
        iut.join()
        connection.close()

