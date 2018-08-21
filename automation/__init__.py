# -*- coding: utf-8 -*-
import logging
import os
import threading
import time

import pika
from event_bus_utils.rmq_handler import RabbitMQHandler, JsonFormatter
from ioppytest import get_from_environment, AMQP_URL, AMQP_EXCHANGE, RESULTS_DIR
from event_bus_utils import AmqpListener, publish_message
from messages import MsgTestingToolTerminate, MsgSessionLog, MsgTestCaseReady, MsgTestingToolReady, \
    MsgTestingToolConfigured, MsgTestSuiteReport, MsgTestCaseVerdict, MsgStepVerifyExecute, \
    MsgTestingToolComponentReady, Message, MsgStepVerifyExecuted, MsgTestSuiteStart, MsgTestCaseStart, MsgTestCaseSkip, \
    MsgTestingToolComponentShutdown

logger = logging.getLogger(__name__)

INTERACTIVE_SESSION = get_from_environment("INTERACTIVE_SESSION", True)
COAP_CLIENT_HOST = get_from_environment("COAP_CLIENT_HOST", 'bbbb::1')
COAP_SERVER_HOST = get_from_environment("COAP_SERVER_HOST", 'bbbb::2')
COAP_SERVER_PORT = get_from_environment("COAP_SERVER_PORT", '5683')

LOG_LEVEL = 30
MAX_LINE_LENGTH = 120


def log_all_received_messages(event_list: list):
    logger.info("Events sniffed in bus: %s" % len(event_list))
    traces_of_all_messages_in_event_bus = ""
    logs_traces_of_all_log_messages_in_event_bus = """ 

*****************************************************************
COMPLETE LOG TRACE from log messages in event bus (MsgSessionLog)
*****************************************************************
    """
    i = 0
    for ev in event_list:
        i += 1
        try:
            traces_of_all_messages_in_event_bus += "\n\tevent count: %s" % i
            traces_of_all_messages_in_event_bus += "\n\tmsg_id: %s" % ev.message_id
            traces_of_all_messages_in_event_bus += "\n\tmsg repr: %s" % repr(ev)[:MAX_LINE_LENGTH]

        except AttributeError as e:
            logger.warning("No message id in message: %s" % repr(ev))

        try:
            if isinstance(ev, MsgSessionLog):
                logs_traces_of_all_log_messages_in_event_bus += "\n[%s] %s" % (ev.component, ev.message)
        except AttributeError as e:
            logger.warning(e)

    logs_traces_of_all_log_messages_in_event_bus += """ 
*****************************************************************
                    END OF LOG TRACE  
*****************************************************************
    """
    logger.info(logs_traces_of_all_log_messages_in_event_bus)
    logger.debug(traces_of_all_messages_in_event_bus)


class MessageLogger(AmqpListener):
    def __init__(self, amqp_url, amqp_exchange):
        AmqpListener.__init__(self, amqp_url, amqp_exchange,
                              callback=self.process_message,
                              topics=['#'],
                              use_message_typing=True)

        self.messages_list = []
        self.messages_by_type_dict = {}

    def process_message(self, message):
   #     logger.debug('[%s]: %s' % (sys._getframe().f_code.co_name, repr(message)[:MAX_LINE_LENGTH]))
        self.messages_list.append(message)
        self.messages_by_type_dict[type(message)] = message

        if isinstance(message, MsgTestingToolTerminate):
            logger.info("Received termination message. Stopping logging")
            self.stop()


class UserMock(threading.Thread):
    """
    this class servers for moking user inputs into GUI
    """
    component_id = 'user_mock'

    # e.g. for TD COAP CORE from 1 to 31
    DEFAULT_TC_LIST = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 32)]

    def __init__(self, iut_testcases=None, iut_to_mock_verifications_for=None):

        self._init_logger()

        threading.Thread.__init__(self)

        self.iut_to_mock_verifications_for = iut_to_mock_verifications_for
        self.event_to_handler_map = {
            MsgTestCaseReady: self.handle_test_case_ready,
            MsgTestingToolReady: self.handle_testing_tool_ready,
            MsgTestingToolConfigured: self.handle_testing_tool_configured,
            MsgTestSuiteReport: self.handle_test_suite_report,
            MsgTestCaseVerdict: self.handle_test_case_verdict,
            MsgTestingToolTerminate: self.handle_testing_tool_terminate,
            MsgStepVerifyExecute: self.handle_verif_step_execute,
            # MsgTestCaseConfiguration: self.handle_test_case_configurate,
        }

        self.shutdown = False
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

        self.message_count = 0

        # queues & default exchange declaration
        if iut_testcases:
            self.implemented_testcases_list = iut_testcases
        else:
            self.implemented_testcases_list = UserMock.DEFAULT_TC_LIST

        queue_name = '%s::eventbus_subscribed_messages' % self.component_id
        self.channel.queue_declare(queue=queue_name, auto_delete=True)

        for ev in self.event_to_handler_map:
            self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                    queue=queue_name,
                                    routing_key=ev.routing_key)

        publish_message(self.connection, MsgTestingToolComponentReady(component=self.component_id))
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.on_request, queue=queue_name)

    def _init_logger(self):
        logger_id = self.component_id
        # init logging to stnd output and log files
        self._logger = logging.getLogger(logger_id)
        self._logger.setLevel(LOG_LEVEL)

        # add stream handler for echoing back into console
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        self._logger.addHandler(ch)

        # AMQP log handler with f-interop's json formatter
        rabbitmq_handler = RabbitMQHandler(AMQP_URL, logger_id)
        json_formatter = JsonFormatter()
        rabbitmq_handler.setFormatter(json_formatter)
        self._logger.addHandler(rabbitmq_handler)

    def log(self, message):
        self._logger.info(message)

    def on_request(self, ch, method, props, body):

        ch.basic_ack(delivery_tag=method.delivery_tag)
        event = Message.load_from_pika(method, props, body)
        self.message_count += 1

        if type(event) in self.event_to_handler_map:
            callback = self.event_to_handler_map[type(event)]
            callback(event)
        else:
            if hasattr(event, 'description'):
                self.log('Event received and ignored: < %s >  %s' % (type(event), event.description))
            else:
                self.log('Event received and ignored: %s' % type(event))

    def handle_verif_step_execute(self, event):

        if event.node in self.iut_to_mock_verifications_for:
            publish_message(self.connection, MsgStepVerifyExecuted(verify_response=True,
                                                                   node=event.node
                                                                   ))
            self.log('Mocked verify response for m: %s (node: %s - step: %s)' %
                     (
                         type(event),
                         event.node,
                         event.step_id,
                     ))

        else:
            self.log('Event received and ignored: %s (node: %s - step: %s)' %
                     (
                         type(event),
                         event.node,
                         event.step_id,
                     ))

    def handle_testing_tool_configured(self, event):
        """
        Behaviour: if tooling configured, then user triggers start of test suite
        """
        m = MsgTestSuiteStart()
        publish_message(self.connection, m)
        self.log('Event received: %s' % type(event))
        self.log('Event description: %s' % event.description)
        self.log('Event pushed: %s' % m)

    def handle_testing_tool_ready(self, event):
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
        self.log('Event received: %s' % type(event))
        # self.log('Event pushed %s' % m)

    def handle_test_case_ready(self, event):
        self.log('Event received: %s' % type(event))
        self.log('Event description: %s' % event.description)

        # m = MsgTestCaseStart()
        # publish_message(self.connection, m)

        if event.testcase_id in self.implemented_testcases_list:
            m = MsgTestCaseStart()
            publish_message(self.connection, m)
            self.log('Event pushed: %s' % m)
        else:
            m = MsgTestCaseSkip(testcase_id=event.testcase_id)
            publish_message(self.connection, m)
            self.log('Event pushed: %s' % m)

    def handle_test_case_verdict(self, event):
        self.log('Event received: %s' % type(event))
        self.log('Event description: %s' % event.description)
        self.log('Got a verdict: %s , complete message: %s' % (event.verdict, repr(event)))

        #  Save verdict
        json_file = os.path.join(
            RESULTS_DIR,
            event.testcase_id + '_verdict.json'
        )
        with open(json_file, 'w') as f:
            f.write(event.to_json())

    def handle_test_suite_report(self, event):
        self.log('Got final report: %s' % event.to_json())

    def handle_testing_tool_terminate(self, event):
        self.log('Event received: %s' % type(event))
        self.log('Event description: %s' % event.description)
        self.log('Terminating execution.. ')
        self.stop()

    def stop(self):
        self.shutdown = True

        if not self.connection.is_open:
            self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        publish_message(self.connection,
                        MsgTestingToolComponentShutdown(component=self.component_id))

        if self.channel.is_open:
            self.channel.stop_consuming()

        self.connection.close()

    def run(self):
        while self.shutdown is False:
            self.connection.process_data_events()
            time.sleep(0.3)
        self.log('%s shutting down..' % self.component_id)