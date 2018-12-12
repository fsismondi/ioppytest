# -*- coding: utf-8 -*-
import os
import time
import json
import pika
import base64
import threading
import logging

from collections import OrderedDict
from event_bus_utils import AmqpListener, publish_message
from event_bus_utils.rmq_handler import RabbitMQHandler, JsonFormatter
from ioppytest import get_from_environment, AMQP_URL, AMQP_EXCHANGE, RESULTS_DIR
from ioppytest.ui_adaptor.message_rendering import (testsuite_results_to_ascii_table,
                                                    testcase_verdict_to_ascii_table,
                                                    testsuite_state_to_ascii_table)

from messages import (MsgTestingToolTerminate, MsgSessionLog,
                      MsgTestCaseReady, MsgTestingToolReady,
                      MsgTestingToolConfigured, MsgTestSuiteReport,
                      MsgTestCaseVerdict, MsgStepVerifyExecute,
                      MsgTestingToolComponentReady, Message,
                      MsgStepVerifyExecuted, MsgTestSuiteStart,
                      MsgTestCaseStart, MsgTestCaseSkip,
                      MsgTestingToolComponentShutdown, MsgSniffingGetCaptureReply,
                      MsgUiRequestSessionConfiguration, MsgUiSessionConfigurationReply)

logger = logging.getLogger(__name__)

COAP_CLIENT_HOST = get_from_environment("COAP_CLIENT_HOST", 'bbbb::1')
COAP_SERVER_HOST = get_from_environment("COAP_SERVER_HOST", 'bbbb::2')
COAP_SERVER_PORT = get_from_environment("COAP_SERVER_PORT", '5683')
TESTSUITE_NAME = os.environ.get('TESTNAME', 'noname')
TESTSUITE_REPORT_DELIM = os.environ.get('DELIM', '===TESTRESULT===')

LOG_LEVEL = 30
MAX_LINE_LENGTH = 120

default_configuration = {
    "testsuite.testcases": None  # None => default config (all test cases)
}


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


class ResultsLogToFile(AmqpListener):
    def __init__(self, amqp_url, amqp_exchange, results_dir=RESULTS_DIR):
        AmqpListener.__init__(self, amqp_url, amqp_exchange,
                              callback=self.process_message,
                              topics=['#'],
                              use_message_typing=True)

        self.results_dir = results_dir
        self.messages_list = []
        self.messages_by_type_dict = {}

    def process_message(self, message):

        if isinstance(message, MsgTestSuiteReport):
            #  Save report
            json_file = os.path.join(self.results_dir, 'final_report.json')
            with open(json_file, 'w') as f:
                f.write(message.to_json())
            logger.info("Saved test suite report file %s" % json_file)

        elif isinstance(message, MsgSniffingGetCaptureReply):
            if message.ok:
                file_path = os.path.join(self.results_dir, message.filename)
                with open(file_path, "wb") as pcap_file:
                    nb = pcap_file.write(base64.b64decode(message.value))
                    logger.info("Saved pcap file %s with %s bytes" % (file_path, nb))
            else:
                logger.warning("Got Capture result reply with NOK field")

        elif isinstance(message, MsgTestCaseVerdict):
            #  Save verdict
            json_file = os.path.join(self.results_dir, message.testcase_id + '_verdict.json')
            with open(json_file, 'w') as f:
                f.write(message.to_json())
            logger.info("Saved verdict file %s for testcase %s" % (json_file, message.testcase_id))

        elif isinstance(message, MsgTestingToolTerminate):
            logger.info("Received termination message. Stopping %s" % self.__class__.__name__)
            self.stop()

        else:
            logger.debug("Ignoring msg: %s" % type(message))


class ResultsLogToStdout(AmqpListener):
    """
    This listener just listens to certain AMQP messages and logs stuff using pretty formatting
    """

    def __init__(self, amqp_url, amqp_exchange, use_special_delimiters_for_report=True):

        self.use_special_delimiters_for_report = use_special_delimiters_for_report
        topics = [
            MsgTestingToolTerminate.routing_key,
            MsgTestCaseVerdict.routing_key,
            MsgTestSuiteReport.routing_key,
        ]

        AmqpListener.__init__(self, amqp_url, amqp_exchange,
                              callback=self.process_message,
                              topics=topics,
                              use_message_typing=True)

    def process_message(self, message):

        if isinstance(message, MsgTestSuiteReport):
            verdict_content = OrderedDict()
            verdict_content['testname'] = TESTSUITE_NAME
            verdict_content.update(message.to_odict())

            # note TESTSUITE_REPORT_DELIM is parsed by continuous interop testing automation components.
            if self.use_special_delimiters_for_report:
                logger.info(
                    "%s %s %s", TESTSUITE_REPORT_DELIM, json.dumps(verdict_content, indent=4), TESTSUITE_REPORT_DELIM)
            else:
                logger.info(
                    "%s: \n%s ", "Test Suite Table Report", testsuite_results_to_ascii_table(message.tc_results))

        elif isinstance(message, MsgTestCaseVerdict):
            verdict_content = OrderedDict()
            verdict_content['testname'] = TESTSUITE_NAME
            verdict_content.update(message.to_odict())
            ascii_table, _ = testcase_verdict_to_ascii_table(message.to_dict())

            logger.info("%s: \n%s ", "Test Case verdict issued", ascii_table)

        elif isinstance(message, MsgTestingToolTerminate):
            logger.info("Received termination message. Stopping %s" % self.__class__.__name__)
            self.stop()

        else:
            logger.warning('Got not expected message type %s' % type(message))


class UIStub(AmqpListener):
    """
    This stub listens and replies to configuration messages (normally responded by the user interface services)
    """

    def __init__(self, amqp_url, amqp_exchange):

        topics = [
            MsgTestingToolTerminate.routing_key,
            MsgUiRequestSessionConfiguration.routing_key,
        ]

        AmqpListener.__init__(self, amqp_url, amqp_exchange,
                              callback=self.process_message,
                              topics=topics,
                              use_message_typing=True)

    def process_message(self, message):

        if isinstance(message, MsgUiRequestSessionConfiguration):
            resp = {
                "configuration": default_configuration,
                "id": '666',
                "testSuite": "someTestingToolName",
                "users": ['pablo', 'bengoechea'],
            }
            m = MsgUiSessionConfigurationReply(
                message,
                **resp
            )
            publish_message(self.connection, m)

        elif isinstance(message, MsgTestingToolTerminate):
            logger.info("Received termination message. Stopping %s" % self.__class__.__name__)
            self.stop()

        else:
            logger.warning('Got not expected message type %s' % type(message))


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
            logger.info("Received termination message. Stopping %s" % self.__class__.__name__)
            self.stop()


class UserMock(threading.Thread):
    """
    this class servers for moking user inputs into GUI
    Behaviour:
        - if iut_testcases is None => all testcases are executed.
        - if iut_to_mock_verifications_for is None => no verif.executed is sent to bus.
    """
    component_id = 'user_mock'

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

        # if implemented_testcases_list is None then all test cases should be executed
        self.implemented_testcases_list = iut_testcases

        # queues & default exchange declaration
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
        self.log('Event ignored: %s' % type(event))

    def handle_test_case_ready(self, event):
        self.log('Event received: %s' % type(event))
        self.log('Event description: %s' % event.description)

        if self.implemented_testcases_list and event.testcase_id not in self.implemented_testcases_list:
            m = MsgTestCaseSkip(testcase_id=event.testcase_id)
            publish_message(self.connection, m)
            self.log('Event pushed: %s' % m)
        else:
            m = MsgTestCaseStart()
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
