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
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE

logger = logging.getLogger(__name__)

COMPONENT_ID = 'automated_iut'

# timeout in seconds
STIMULI_HANDLER_TOUT = 10

# IUT_CMD = [
#     'python',
#     'automated_IUTs/coap_client_coapthon/CoAPthon/coapclient.py'
# ]
#
#
# # mapping message's stimuli id -> CoAPthon (coap client) commands
# stimuli_cmd_dict = {
# 'TD_COAP_CORE_01_v01_step_01' :  IUT_CMD + ['-o', 'GET', '-p', 'coap://127.0.0.1:5683/test', ],
# 'TD_COAP_CORE_01_v01_step_02' :  IUT_CMD + ['-o', 'GET', '-p', 'coap://127.0.0.1:5683/test', ],
# }

IUT_CMD = [
    'python',
    'automated_IUTs/coap_client_coapthon/CoAPthon/finterop_interop_tests.py',
    '-t',
]

# mapping message's stimuli id -> CoAPthon (coap client) commands
stimuli_cmd_dict = {
    'TD_COAP_CORE_01_v01_step_01': IUT_CMD + ['test_td_coap_core_01'],
    'TD_COAP_CORE_02_v01_step_01': IUT_CMD + ['test_td_coap_core_02'],
    'TD_COAP_CORE_03_v01_step_01': IUT_CMD + ['test_td_coap_core_03'],
    'TD_COAP_CORE_04_v01_step_01': IUT_CMD + ['test_td_coap_core_04'],
    'TD_COAP_CORE_05_v01_step_01': IUT_CMD + ['test_td_coap_core_05'],
    'TD_COAP_CORE_06_v01_step_01': IUT_CMD + ['test_td_coap_core_06'],
    'TD_COAP_CORE_07_v01_step_01': IUT_CMD + ['test_td_coap_core_07'],
    'TD_COAP_CORE_08_v01_step_01': IUT_CMD + ['test_td_coap_core_08'],
    'TD_COAP_CORE_09_v01_step_01': IUT_CMD + ['test_td_coap_core_09'],
    'TD_COAP_CORE_10_v01_step_01': IUT_CMD + ['test_td_coap_core_10'],
}
skip_list = [
    'TD_COAP_CORE_11_v01'
    'TD_COAP_CORE_11_v01'
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


class AutomatedIUT(threading.Thread):
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

        elif isinstance(event, MsgTestCaseReady) and event.testcase_id in skip_list:
            publish_message(self.channel, MsgTestCaseSkip(testcase_id=event.testcase_id))

        elif isinstance(event, MsgStepExecute):

            if event.node == 'coap_client' and event.step_type == 'stimuli' and event.step_id in stimuli_cmd_dict:
                cmd = stimuli_cmd_dict[event.step_id]
                step = event.step_id

                self._execute_stimuli(step, cmd )

            elif event.node == 'coap_client' and event.step_type == 'verify':
                step = event.step_id
                self._execute_verify(step)

            else:
                logging.info('Event received and ignored: %s' % event.to_json())

        elif isinstance(event, MsgTestSuiteReport):
            logging.info('Test suite finished, final report: %s' % event.to_json())
            self._exit

        else:
            logging.info('Event received and ignored: %s' % event._type)

    def _exit(self):
        time.sleep(2)
        self.connection.close()
        sys.exit(0)

    def _execute_verify(self, verify_step_id, ):
        logging.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)
        publish_message(self.channel, MsgVerifyResponse(verify_response=True))

    def _execute_stimuli(self, stimuli_step_id, cmd):
        try:
            logging.info('spawning process with : %s' % cmd)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            proc.wait(timeout=STIMULI_HANDLER_TOUT)
            output = ''
            while proc.poll() is None:
                output += str(proc.stdout.readline())
            output += str(proc.stdout.read())
            logging.info('%s executed' % stimuli_step_id)
            logging.info('process stdout: %s' % output)

        except subprocess.TimeoutExpired as tout:
            logging.warning('Process timeout. info: %s' % str(tout))

        publish_message(self.channel, MsgStimuliExecuted())

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

    iut = AutomatedIUT(connection)
    iut.start()
    iut.join()
    connection.close()
