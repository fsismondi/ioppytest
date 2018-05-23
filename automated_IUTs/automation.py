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

from ioppytest.utils.messages import *
from ioppytest.utils.amqp_synch_call import publish_message
from ioppytest import AMQP_URL, AMQP_EXCHANGE, INTERACTIVE_SESSION, RESULTS_DIR, LOG_LEVEL

# timeout in seconds
STIMULI_HANDLER_TOUT = 10

COMPONENT_ID = 'automation'

logger = logging.getLogger(COMPONENT_ID)
logger.setLevel(LOG_LEVEL)


@property
def NotImplementedField(self):
    raise NotImplementedError


def signal_int_handler(signal, frame):
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

    publish_message(
        connection,
        MsgTestingToolComponentShutdown(component=COMPONENT_ID)
    )

    logger.info('got SIGINT. Bye bye!')

    sys.exit(0)


signal.signal(signal.SIGINT, signal_int_handler)


class AutomatedIUT(threading.Thread):
    # attributes to be provided by subclass
    implemented_testcases_list = NotImplementedField
    implemented_stimuli_list = NotImplementedField
    component_id = NotImplementedField
    node = NotImplementedField

    EVENTS = [
        MsgTestCaseReady,
        MsgTestCaseConfiguration,
        MsgStepVerifyExecute,
        MsgStepStimuliExecute,
        MsgTestSuiteReport,
        MsgTestingToolTerminate,
    ]

    def __init__(self, node):

        self.node = node

        # lets setup the AMQP stuff
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()
        threading.Thread.__init__(self)
        self.message_count = 0

        # queues & default exchange declaration
        services_queue_name = '%s::testsuiteEvents' % self.component_id
        self.channel.queue_declare(queue=services_queue_name, auto_delete=True)

        for ev in self.EVENTS:
            self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                    queue=services_queue_name,
                                    routing_key=ev.routing_key)
        # send hello message
        publish_message(self.connection, MsgTestingToolComponentReady(component=self.component_id))
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.on_request, queue=services_queue_name)

        # # # #  INTERFACE to be overridden by child class # # # # # # # # # # # # # # # # # #

    def _exit(self):
        m = MsgTestingToolComponentShutdown(component=self.component_id)
        publish_message(self.connection, m)
        time.sleep(2)
        self.connection.close()
        sys.exit(0)

    def _execute_verify(self, verify_step_id):
        """
        If IUT cannot perform verify validations then just override method with `pass` command

        :param verify_step_id:
        :return:
        """
        raise NotImplementedError("Subclasses should implement this!")

    def _execute_stimuli(self, stimuli_step_id, addr):
        """
        When executing IUT stimuli, the call MUST NOT block thread forever

        :param stimuli_step_id:
        :param addr:
        :return:
        """
        raise NotImplementedError("Subclasses should implement this!")

    # TODO fix me! no node should be passed, mabe pass config ID (test description defines one)
    def _execute_configuration(self, testcase_id, node):
        """
        If IUT doesnt need to configure anything then just override method with `pass` command

        :param testcase_id:
        :param node:
        :return:
        """
        raise NotImplementedError("Subclasses should implement this!")

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def run(self):
        logger.info("Starting thread listening on the event bus")
        self.channel.start_consuming()
        logger.info('Bye byes!')

    def stop(self):

        self.channel.stop_consuming()

    def on_request(self, ch, method, props, body):

        ch.basic_ack(delivery_tag=method.delivery_tag)

        event = Message.load_from_pika(method, props, body)

        self.message_count += 1

        if event is None:
            return

        logger.info('Event received: %s' % repr(event))

        if isinstance(event, MsgTestCaseReady):
            if event.testcase_id not in self.implemented_testcases_list:
                time.sleep(0.1)
                logger.info('IUT %s pushing test case skip message for %s' % (self.component_id, event.testcase_id))
                publish_message(self.connection, MsgTestCaseSkip(testcase_id=event.testcase_id))
            else:
                logger.info('IUT %s ready to execute testcase' % self.component_id)

        elif isinstance(event, MsgStepStimuliExecute):
            logger.info('event.node %s,%s' % (event.node, self.node))
            if event.node == self.node and event.step_id in self.implemented_stimuli_list:
                step = event.step_id
                addr = event.target_address # may be None

                self._execute_stimuli(step, addr)  # blocking till stimuli execution
                publish_message(self.connection, MsgStepStimuliExecuted(node=self.node))
            else:
                logger.info('Event received and ignored: \n\tEVENT:%s \n\tNODE:%s \n\tSTEP: %s' %
                            (
                                type(event),
                                event.node,
                                event.step_id,
                            ))

        elif isinstance(event, MsgStepVerifyExecute):

            if event.node == self.node:
                step = event.step_id
                self._execute_verify(step)
                publish_message(self.connection, MsgStepVerifyExecuted(verify_response=True,
                                                                       node=self.node
                                                                       ))
            else:
                logger.info('Event received and ignored: %s (node: %s - step: %s)' %
                            (
                                type(event),
                                event.node,
                                event.step_id,
                            ))

        elif isinstance(event, MsgTestSuiteReport):
            logger.info('Got final test suite report: %s' % event.to_json())

        elif isinstance(event, MsgTestingToolTerminate):
            logger.info('Test terminate signal received. Quitting..')
            time.sleep(2)
            self._exit()

        elif isinstance(event, MsgConfigurationExecute):
            if event.node == self.node:
                logger.info('Configure test case %s', event.testcase_id)
                # TODO fix me _execute_config should pass an arbitrary dict, which will be used later for building the fields of the ret message
                ipaddr = self._execute_configuration(event.testcase_id,
                                                     event.node)  # blocking till complete config execution
                if ipaddr != '':
                    m = MsgConfigurationExecuted(testcase_id=event.testcase_id, node=event.node, ipv6_address=ipaddr)
                    publish_message(self.connection, m)
        else:
            logger.info('Event received and ignored: %s' % type(event))


class UserMock(threading.Thread):
    """
    this class servers for moking user inputs into GUI
    """
    component_id = 'user_mock'

    # e.g. for TD COAP CORE from 1 to 31
    DEFAULT_TC_LIST = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 31)]

    EVENTS = [
        MsgTestCaseReady,
        MsgTestingToolReady,
        MsgTestingToolConfigured,
        MsgTestCaseConfiguration,
        MsgTestCaseVerdict,
        MsgTestSuiteReport,
        MsgTestingToolTerminate,
    ]

    def __init__(self, iut_testcases=None):

        threading.Thread.__init__(self)

        self.shutdown = False
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

        self.message_count = 0
        # queues & default exchange declaration

        if iut_testcases:
            self.implemented_testcases_list = iut_testcases
        else:
            self.implemented_testcases_list = UserMock.DEFAULT_TC_LIST

        services_queue_name = '%s::testsuiteEvents' % self.component_id
        self.channel.queue_declare(queue=services_queue_name, auto_delete=True)

        for ev in self.EVENTS:
            self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                    queue=services_queue_name,
                                    routing_key=ev.routing_key)

        publish_message(self.connection, MsgTestingToolComponentReady(component=self.component_id))
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.on_request, queue=services_queue_name)

    def on_request(self, ch, method, props, body):

        ch.basic_ack(delivery_tag=method.delivery_tag)

        event = Message.load_from_pika(method, props, body)

        self.message_count += 1

        if event is None:
            return

        elif isinstance(event, MsgTestingToolReady):
            # m = MsgSessionConfiguration(
            #     configuration={
            #         "testsuite.testcases": [
            #             "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
            #             "http://doc.f-interop.eu/tests/TD_COAP_CORE_02",
            #             "http://doc.f-interop.eu/tests/TD_COAP_CORE_03",
            #         ]
            #     }
            # )  # from TC1 to TC3
            #
            # publish_message(self.connection, m)
            logger.info('Event received %s' % type(event))
            # logger.info('Event pushed %s' % m)

        elif isinstance(event, MsgTestingToolConfigured):
            m = MsgTestSuiteStart()
            publish_message(self.connection, m)
            logger.info('Event received %s' % type(event))
            logger.info('Event description %s' % event.description)
            logger.info('Event pushed %s' % m)

        elif isinstance(event, MsgTestCaseReady):
            logger.info('Event received %s' % type(event))
            logger.info('Event description %s' % event.description)

            # m = MsgTestCaseStart()
            # publish_message(self.connection, m)

            if event.testcase_id in self.implemented_testcases_list:
                m = MsgTestCaseStart()
                publish_message(self.connection, m)

                logger.info('Event pushed %s' % m)
            else:
                m = MsgTestCaseSkip(testcase_id=event.testcase_id)
                publish_message(self.connection, m)
                logger.info('Event pushed %s' % m)

        elif isinstance(event, MsgTestCaseVerdict):
            logger.info('Event received %s' % type(event))
            logger.info('Event description %s' % event.description)
            logger.info('Got a verdict: %s , complete message %s' % (event.verdict, repr(event)))

            #  Save verdict
            json_file = os.path.join(
                RESULTS_DIR,
                event.testcase_id + '_verdict.json'
            )
            with open(json_file, 'w') as f:
                f.write(event.to_json())

        elif isinstance(event, MsgTestSuiteReport):
            logger.info('Got final report: %s' % event.to_json())

        elif isinstance(event, MsgTestingToolTerminate):
            logger.info('Event received %s' % type(event))
            logger.info('Event description %s' % event.description)
            logger.info('Terminating execution.. ')
            self.stop()

        else:
            if hasattr(event, 'description'):
                logger.info('Event received and ignored < %s >  %s' % (type(event), event.description))
            else:
                logger.info('Event received and ignored: %s' % type(event))

    def stop(self):
        self.shutdown = True
        publish_message(self.connection,
                        MsgTestingToolComponentShutdown(component=COMPONENT_ID))
        self.channel.stop_consuming()
        self.connection.close()

    def exit(self):
        logger.info('%s exiting..' % self.component_id)

    def run(self):
        while self.shutdown is False:
            self.connection.process_data_events()
            time.sleep(0.3)

        logger.info('%s shutting down..' % self.component_id)
        self.exit()
