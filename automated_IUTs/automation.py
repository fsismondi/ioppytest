# -*- coding: utf-8 -*-
# !/usr/bin/env python3

"""
Example of python code for implementing an automated IUT.
AutomatedIUT class provides an interface for automated IUTs implementations.
"""

import pika
import threading
import logging
import sys
import signal
from coap_testing_tool.utils.event_bus_messages import *
from coap_testing_tool.utils.amqp_synch_call import publish_message
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE, INTERACTIVE_SESSION

logger = logging.getLogger(__name__)

# timeout in seconds
STIMULI_HANDLER_TOUT = 10

COMPONENT_ID = 'automation'


@property
def NotImplementedField(self):
    raise NotImplementedError


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
    # attributes to be provided by subclass
    implemented_testcases_list = NotImplementedField
    stimuli_cmd_dict = NotImplementedField
    component_id = NotImplementedField
    node = NotImplementedField

    def __init__(self):

        # lets create connection
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        self.channel = self.connection.channel()

        # in case exchange not not declared
        self.connection.channel().exchange_declare(exchange=AMQP_EXCHANGE,
                                                   type='topic',
                                                   durable=True,
                                                   )
        threading.Thread.__init__(self)
        self.message_count = 0
        # queues & default exchange declaration

        services_queue_name = 'services_queue@%s' % self.component_id
        self.channel.queue_declare(queue=services_queue_name, auto_delete=True)
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=services_queue_name,
                                routing_key='control.testcoordination')
        publish_message(self.channel, MsgTestingToolComponentReady(component=self.component_id))
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.on_request, queue=services_queue_name)

    def run(self):
        print("Starting thread listening on the event bus")
        self.channel.start_consuming()
        print('Bye byes!')

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
            if event.testcase_id not in self.implemented_testcases_list:
                publish_message(self.channel, MsgTestCaseSkip(testcase_id=event.testcase_id))
            else:
                logging.info('IUT %s ready to execute testcase' % self.component_id)

        elif isinstance(event, MsgStepStimuliExecute):

            if event.node == self.node and event.step_id in self.stimuli_cmd_dict:
                cmd = self.stimuli_cmd_dict[event.step_id]
                step = event.step_id
                if cmd:
                    self._execute_stimuli(step, cmd)
                publish_message(self.channel, MsgStepStimuliExecuted(node=self.node))
            else:
                logging.info('Event received and ignored: %s (node: %s - step: %s)' %
                             (
                                 event._type,
                                 event.node,
                                 event.step_id,
                             ))

        elif isinstance(event, MsgStepVerifyExecute):

            if event.node == self.node:
                step = event.step_id
                self._execute_verify(step)
                publish_message(self.channel, MsgStepVerifyExecuted(verify_response=True,
                                                                    node=self.node
                                                                    ))
            else:
                logging.info('Event received and ignored: %s (node: %s - step: %s)' %
                             (
                                 event._type,
                                 event.node,
                                 event.step_id,
                             ))

        elif isinstance(event, MsgTestSuiteReport):
            logging.info('Test suite finished, final report: %s' % event.to_json())

        else:
            logging.info('Event received and ignored: %s' % event._type)

    def _exit(self):
        time.sleep(2)
        self.connection.close()
        sys.exit(0)

    def _execute_verify(self, verify_step_id, ):
        raise NotImplementedError("Subclasses should implement this!")

    def _execute_stimuli(self, stimuli_step_id, cmd):
        raise NotImplementedError("Subclasses should implement this!")


class UserEmulator(threading.Thread):
    """
    this class servers for moking user inputs into GUI
    """
    component_id = 'user_emulation'

    DEFAULT_TC_LIST = [
        'TD_COAP_CORE_01_v01',
        'TD_COAP_CORE_02_v01',
    ]

    def __init__(self, connection, iut_node, iut_testcases=None):
        threading.Thread.__init__(self)
        self.message_count = 0
        # queues & default exchange declaration
        self.iut_node = iut_node

        if iut_testcases:
            self.implemented_testcases_list = iut_testcases
        else:
            self.implemented_testcases_list = UserEmulator.DEFAULT_TC_LIST

        self.connection = connection
        self.channel = connection.channel()
        services_queue_name = 'services_queue@%s' % self.component_id
        self.channel.queue_declare(queue=services_queue_name, auto_delete=True)

        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=services_queue_name,
                                routing_key='control.testcoordination')

        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=services_queue_name,
                                routing_key='control.session')

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

        elif isinstance(event, MsgTestingToolReady):
            m = MsgTestSuiteStart()
            publish_message(self.channel, m)
            logging.info('Event received %s' % event._type)
            logging.info('Event pushed %s' % m)

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
