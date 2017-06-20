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
from automated_IUTs import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST

logger = logging.getLogger(__name__)

COMPONENT_ID = 'automated_iut'
str_coap_server_port = str(COAP_SERVER_PORT)
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
    'java -jar automated_IUTs/coap_client_californium/target/coap_plugtest_client-1.1.0-SNAPSHOT.jar -s -u coap://['
    + COAP_SERVER_HOST + ']:' + str_coap_server_port + ' -t'
]

# mapping message's stimuli id -> CoAPthon (coap client) commands
stimuli_cmd_dict = {
    'TD_COAP_CORE_01_v01_step_01': IUT_CMD + ['TD_COAP_CORE_01'],
    'TD_COAP_CORE_02_v01_step_01': IUT_CMD + ['TD_COAP_CORE_02'],
    'TD_COAP_CORE_03_v01_step_01': IUT_CMD + ['TD_COAP_CORE_03'],
    'TD_COAP_CORE_04_v01_step_01': IUT_CMD + ['TD_COAP_CORE_04'],
    'TD_COAP_CORE_05_v01_step_01': IUT_CMD + ['TD_COAP_CORE_05'],
    'TD_COAP_CORE_06_v01_step_01': IUT_CMD + ['TD_COAP_CORE_06'],
    'TD_COAP_CORE_07_v01_step_01': IUT_CMD + ['TD_COAP_CORE_07'],
    'TD_COAP_CORE_08_v01_step_01': IUT_CMD + ['TD_COAP_CORE_08'],
    'TD_COAP_CORE_09_v01_step_01': IUT_CMD + ['TD_COAP_CORE_09'],
    'TD_COAP_CORE_10_v01_step_01': IUT_CMD + ['TD_COAP_CORE_10'],
    'TD_COAP_CORE_11_v01_step_01': IUT_CMD + ['TD_COAP_CORE_11'],
    'TD_COAP_CORE_12_v01_step_01': IUT_CMD + ['TD_COAP_CORE_12'],
    'TD_COAP_CORE_13_v01_step_01': IUT_CMD + ['TD_COAP_CORE_13'],
    'TD_COAP_CORE_14_v01_step_01': IUT_CMD + ['TD_COAP_CORE_14'],
    'TD_COAP_CORE_17_v01_step_01': IUT_CMD + ['TD_COAP_CORE_17'],
    'TD_COAP_CORE_18_v01_step_01': IUT_CMD + ['TD_COAP_CORE_18'],
    'TD_COAP_CORE_19_v01_step_01': IUT_CMD + ['TD_COAP_CORE_19'],
    'TD_COAP_CORE_20_v01_step_01': IUT_CMD + ['TD_COAP_CORE_20'],
    'TD_COAP_CORE_20_v01_step_05': None,
    'TD_COAP_CORE_21_v01_step_01': IUT_CMD + ['TD_COAP_CORE_21'],
    'TD_COAP_CORE_21_v01_step_05': None,
    'TD_COAP_CORE_21_v01_step_09': None,
    'TD_COAP_CORE_21_v01_step_10': None,
    'TD_COAP_CORE_22_v01_step_01': IUT_CMD + ['TD_COAP_CORE_22'],
    'TD_COAP_CORE_22_v01_step_04': None,
    'TD_COAP_CORE_22_v01_step_08': None,
    'TD_COAP_CORE_22_v01_step_12': None,
    'TD_COAP_CORE_22_v01_step_13': None,
    'TD_COAP_CORE_23_v01_step_01': IUT_CMD + ['TD_COAP_CORE_23'],
    'TD_COAP_CORE_23_v01_step_05': None,

}
skip_list = [
    'TD_COAP_CORE_15_v01'
    'TD_COAP_CORE_16_v01'
    'TD_COAP_CORE_31_v01'
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
                if cmd:
                    self._execute_stimuli(step, cmd)
                publish_message(self.channel, MsgStimuliExecuted())

            elif event.node == 'coap_client' and event.step_type == 'verify':
                step = event.step_id
                self._execute_verify(step)
                publish_message(self.channel, MsgVerifyResponse(verify_response=True))

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

    def _execute_stimuli(self, stimuli_step_id, cmd):
        try:
            logging.info('spawning process with : %s' % cmd)
            cmd=" ".join(cmd)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
            proc.wait(timeout=STIMULI_HANDLER_TOUT)
            output = ''
            while proc.poll() is None:
                output += str(proc.stdout.readline())
            output += str(proc.stdout.read())
            logging.info('%s executed' % stimuli_step_id)
            logging.info('process stdout: %s' % output)

        except subprocess.TimeoutExpired as tout:
            logging.warning('Process timeout. info: %s' % str(tout))

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
