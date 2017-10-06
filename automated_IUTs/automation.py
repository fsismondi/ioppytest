# -*- coding: utf-8 -*-
# !/usr/bin/env python3

"""
Example of python code for implementing an automated IUT.
AutomatedIUT class provides an interface for automated IUTs implementations.
"""

import os
import sys
import pika
import signal
import logging
import threading

from coap_testing_tool.utils.event_bus_messages import *
from coap_testing_tool.utils.amqp_synch_call import publish_message
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE, INTERACTIVE_SESSION, RESULTS_DIR

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

    def __init__(self, node):

        self.node = node

        # lets setup the AMQP stuff
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()
        threading.Thread.__init__(self)
        self.message_count = 0

        # queues & default exchange declaration
        services_queue_name = 'services_queue@%s' % self.component_id
        self.channel.queue_declare(queue=services_queue_name, auto_delete=True)
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=services_queue_name,
                                routing_key='control.testcoordination')
        # send hello message
        publish_message(self.channel, MsgTestingToolComponentReady(component=self.component_id))
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.on_request, queue=services_queue_name)

    def run(self):
        logger.info("Starting thread listening on the event bus")
        self.channel.start_consuming()
        logger.info('Bye byes!')

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

        logging.info('Event received: %s' % repr(event))

        if isinstance(event, MsgTestCaseReady):
            if event.testcase_id not in self.implemented_testcases_list:
                time.sleep(0.1)
                logging.info('IUT %s pushing test case skip message for %s' % (self.component_id, event.testcase_id))
                publish_message(self.channel, MsgTestCaseSkip(testcase_id=event.testcase_id))
            else:
                logging.info('IUT %s ready to execute testcase' % self.component_id)

        elif isinstance(event, MsgStepStimuliExecute):
            logging.info('event.node %s,%s' % (event.node, self.node))
            if event.node == self.node and event.step_id in self.stimuli_cmd_dict:
                # TODO Fix me: No  need to go fetch CMD to child object, just call as _execute_simuli(step_id,target_address)
                cmd = self.stimuli_cmd_dict[event.step_id]
                step = event.step_id
                addr = event.target_address
                if cmd:
                    self._execute_stimuli(step, cmd,
                                          addr)  # this should be a blocking call until stimuli has been executed
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

        elif isinstance(event, MsgTestingToolTerminate):
            logging.info('Test terminate signal received. Quitting..')
            time.sleep(2)
            self._exit

        elif isinstance(event, MsgConfigurationExecute):
            if event.node == self.node:
                logging.info('Configure test case %s', event.testcase_id)
                # TODO fix me _execute_config should pass an arbitrary dict, which will be used later for building the fields of the ret message
                ipaddr = self._execute_configuration(event.testcase_id,
                                                     event.node)  # this should be a blocking call until configuration has been done
                if ipaddr != '':
                    m = MsgConfigurationExecuted(testcase_id=event.testcase_id, node=event.node, ipv6_address=ipaddr)
                    publish_message(self.channel, m)
        else:
            logging.info('Event received and ignored: %s' % event._type)

    def _exit(self):
        m = MsgTestingToolComponentShutdown(component=self.component_id)
        publish_message(self.channel, m)
        time.sleep(2)
        self.connection.close()
        sys.exit(0)

    def _execute_verify(self, verify_step_id):
        raise NotImplementedError("Subclasses should implement this!")

    # TODO fix me! no cmd should be passed, this is child class related stuff
    def _execute_stimuli(self, stimuli_step_id, cmd, addr):
        raise NotImplementedError("Subclasses should implement this!")

    # TODO fix me! no node should be passed, mabe pass config ID (test description defines one)
    def _execute_configuration(self, testcase_id, node):
        raise NotImplementedError("Subclasses should implement this!")


class UserMock(threading.Thread):
    """
    this class servers for moking user inputs into GUI
    """
    component_id = 'user_mock'

    # e.g. for TD COAP CORE from 1 to 31
    DEFAULT_TC_LIST = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 31)]

    def __init__(self, connection, iut_testcases=None):
        threading.Thread.__init__(self)
        self.message_count = 0
        # queues & default exchange declaration

        if iut_testcases:
            self.implemented_testcases_list = iut_testcases
        else:
            self.implemented_testcases_list = UserMock.DEFAULT_TC_LIST

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
            logging.info('Event description %s' % event.description)
            logging.info('Event pushed %s' % m)

        elif isinstance(event, MsgTestCaseReady):
            logging.info('Event received %s' % event._type)
            logging.info('Event description %s' % event.description)

            if event.testcase_id in self.implemented_testcases_list:
                m = MsgTestCaseStart()
                publish_message(self.channel, m)

                logging.info('Event pushed %s' % m)
            else:
                m = MsgTestCaseSkip(testcase_id=event.testcase_id)
                publish_message(self.channel, m)
                logging.info('Event pushed %s' % m)

        elif isinstance(event, MsgTestCaseVerdict):
            logging.info('Event received %s' % event._type)
            logging.info('Event description %s' % event.description)
            logging.info('Got a verdict: %s , complete message %s' % (event.verdict, repr(event)))

            #  Save verdict
            json_file = os.path.join(
                RESULTS_DIR,
                event.testcase_id + '_verdict.json'
            )
            with open(json_file, 'w') as f:
                f.write(event.to_json())

        elif isinstance(event, MsgTestSuiteReport):
            logging.info('Test suite finished, final report: %s' % event.to_json())
            time.sleep(2)
            m = MsgTestingToolTerminate()
            publish_message(self.channel, m)
            time.sleep(2)

        elif isinstance(event, MsgTestingToolTerminate):
            logging.info('Event received %s' % event._type)
            logging.info('Event description %s' % event.description)
            logging.info('Terminating execution.. ')
            time.sleep(2)
            self._exit()

        elif isinstance(event, MsgStepStimuliExecute):
            logging.info('Message received %s . IUT node: %s ' % (event._type, event.node))
            logging.info('Event description %s' % event.description)

        elif isinstance(event, MsgStepVerifyExecute):
            logging.info('Message received %s . IUT node: %s ' % (event._type, event.node))
            logging.info('Event description %s' % event.description)

        elif isinstance(event, MsgTestingToolComponentReady) or isinstance(event, MsgTestingToolComponentShutdown):
            logging.info('Message received %s . Component: %s ' % (event._type, event.component))

        else:

            if hasattr(event, 'description'):
                logging.info('Event received and ignored < %s >  %s' % (event._type, event.description))
            else:
                logging.info('Event received and ignored: %s' % event._type)

    def _exit(self):
        m = MsgTestingToolComponentShutdown(component=COMPONENT_ID)
        publish_message(self.channel, m)
        time.sleep(2)
        self.connection.close()
        sys.exit(0)

    def run(self):
        print("Starting thread listening on the event bus")
        self.channel.start_consuming()
        print('Bye byes!')
