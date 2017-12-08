# -*- coding: utf-8 -*-
# !/usr/bin/env python3

from ioppytest.utils.messages import *
from ioppytest.utils.amqp_synch_call import publish_message
from tests import MessageGenerator

from tests.pcap_base64_examples import *
from urllib.parse import urlparse
import logging

import unittest
import pika
import sys
import time
import os
import threading
import datetime

COMPONENT_ID = 'fake_session'
MESSAGES_WAIT_INTERVAL = 1  # in seconds
AMQP_EXCHANGE = ''
AMQP_URL = ''
message_count = 0
stop_generator_signal = False

default_configuration = {
    "testsuite.testcases": [
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_02",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_03"
    ]
}

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

logging.getLogger('pika').setLevel(logging.INFO)

# queue which tracks all non answered services requests
services_mid_backlog = []
services_events_tracelog = []

"""
PRE-CONDITIONS:
- Export AMQP_URL in the running environment
- Have CoAP testing tool running & listening to the bus
"""

# for a typical user input, for a user (coap client) vs automated-iut ( coap server) session type:
user_sequence = [
    MsgTestSuiteGetStatus(),
    MsgTestSuiteGetStatus(),
    MsgTestCaseSkip(testcase_id='TD_COAP_CORE_02'),
    MsgTestSuiteGetStatus(),
    MsgTestCaseSkip(testcase_id='TD_COAP_CORE_03'),
    MsgTestSuiteGetStatus(),
    MsgTestCaseStart(),  # execute TC1  ( w/ no IUT in the bus )
    MsgTestSuiteGetStatus(),
    MsgStepStimuliExecuted(),
    MsgTestSuiteGetStatus(),
    MsgStepVerifyExecuted(),
    MsgTestSuiteGetStatus(),
    MsgStepVerifyExecuted(
        verify_response=False,
        description='User indicates that IUT didnt behave as expected '),
    MsgTestSuiteGetStatus(),  # at this point we should see a TC verdict
    MsgTestCaseRestart(),
    MsgTestSuiteGetStatus(),
    MsgTestSuiteAbort(),
    MsgTestSuiteGetStatus(),
]

service_api_calls = [

    # TAT calls
    MsgTestSuiteGetStatus(),
    MsgTestSuiteGetTestCases(),
    MsgInteropTestCaseAnalyze(
        testcase_id="TD_COAP_CORE_01",
        testcase_ref="http://f-interop.paris.inria.fr/tests/TD_COAP_CORE_01",
        file_enc="pcap_base64",
        filename="TD_COAP_CORE_01.pcap",
        value=PCAP_TC_COAP_01_base64,
    ),

    # Sniffer calls (order matters!)
    MsgSniffingStart(
        capture_id='TD_COAP_CORE_01',
        filter_if='tun0',
        filter_proto='udp'
    ),
    MsgSniffingStop(),
    MsgSniffingGetCapture(tescase_id='TD_COAP_CORE_01'),
    MsgSniffingGetCaptureLast(),

    # Dissector calls
    MsgDissectionDissectCapture(),
    MsgDissectionDissectCapture(
        file_enc="pcap_base64",
        filename="TD_COAP_CORE_01.pcap",
        protocol_selection='coap',
        value=PCAP_TC_COAP_01_base64,
    ),
    # complete dissection of pcap
    MsgDissectionDissectCapture(
        file_enc="pcap_base64",
        filename="TD_COAP_CORE_01.pcap",
        value=PCAP_TC_COAP_01_base64,
    ),
    # complete dissection of pcap with extra TCP traffic
    MsgDissectionDissectCapture(
        file_enc="pcap_base64",
        filename="TD_COAP_CORE_01.pcap",
        value=PCAP_TC_COAP_01_mingled_with_tcp_traffic_base64,
    ),
    # same as dis4 but filtering coap messages
    MsgDissectionDissectCapture(
        file_enc="pcap_base64",
        filename="TD_COAP_CORE_01.pcap",
        protocol_selection='coap',
        value=PCAP_TC_COAP_01_mingled_with_tcp_traffic_base64,
    ),

    # this should generate an error
    MsgTestCaseSkip(testcase_id='TD_COAP_CORE_04'),

    # pcap sniffed using AMQP based packet sniffer
    MsgDissectionDissectCapture(
        file_enc="pcap_base64",
        filename="TD_COAP_CORE_01.pcap",
        value=PCAP_COAP_GET_OVER_TUN_INTERFACE_base64,
    )
]


class ApiTests(unittest.TestCase):
    """
    python3 -m unittest tests/test_api.py -vvv
    """

    def setUp(self):

        global stop_generator_signal
        stop_generator_signal = False

        import_env_vars()

        self.conn = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        self.channel = self.conn.channel()

        # MESSAGE VALIDATOR BOUND TO THE CONTROL EVENTS QUEUE
        control_queue_name = 'control_queue@%s' % COMPONENT_ID

        # lets' first clean up the queue
        self.channel.queue_delete(queue=control_queue_name)
        self.channel.queue_declare(queue=control_queue_name, auto_delete=True)
        self.channel.queue_bind(exchange=AMQP_EXCHANGE, queue=control_queue_name, routing_key='control.#')
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(validate_message, queue=control_queue_name)

        # ERROR MSG VERIFIER BOUND TO ERRORS LOGS AND OTHER ERROR EVENTS QUEUE
        errors_queue_name = 'bus_errors_queue@%s' % COMPONENT_ID
        # lets' first clean up the queue
        self.channel.queue_delete(queue=errors_queue_name)

        self.channel.queue_declare(queue=errors_queue_name, auto_delete=True)
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=errors_queue_name,
                                routing_key='log.error.*')

        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=errors_queue_name,
                                routing_key='control.session.error')

        # for getting the terminate signal
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=errors_queue_name,
                                routing_key=MsgTestingToolTerminate.routing_key)
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(check_for_bus_error, queue=errors_queue_name)

    def tearDown(self):
        self.conn.close()

    def test_user_emulation(self):
        """
        This basically checks that the testing tool doesnt crash while user is pushing message inputs into to the bus.
        We check for:
        - log errors in the bus
        - malformed messages in the bus

        """

        # prepare the message generator
        messages = []  # list of messages to send
        messages += user_sequence
        messages.append(MsgTestingToolTerminate())  # message that triggers stop_generator_signal

        thread_msg_gen = MessageGenerator(
            amqp_url=AMQP_URL,
            amqp_exchange=AMQP_EXCHANGE,
            messages_list=messages,
            wait_time_between_pubs=MESSAGES_WAIT_INTERVAL
        )
        logger.debug("Starting Message Generator thread ")

        publish_message(self.conn, MsgSessionConfiguration(
            configuration=default_configuration))  # this prepares the FSM of the coordinator
        publish_message(self.conn, MsgTestSuiteStart())  # this prepares the FSM of the coordinator
        time.sleep(10)  # wait for the testing tool to enter test suite ready state

        thread_msg_gen.start()
        try:
            self.channel.start_consuming()
        except Exception as e:
            thread_msg_gen.stop()
            assert False, str(e)

    def test_testing_tool_internal_services(self):
        """
        This checks for:
         - log errors in the bus
         - malformed messages in the bus
         - request reply correlation (there's one response per each request)
        """
        global COMPONENT_ID

        # some non request/response messages types exchanged during a session
        events_to_ignore = [
            'testingtool.ready',
            'testingtool.component.ready',
            'agent.configured',
            'session.interop.configuration',  # TODO depricate this
            'session.configuration',
            'testingtool.configured',
        ]

        # auxiliary function
        def check_for_correlated_request_reply(ch, method, props, body):

            global services_mid_backlog
            global services_events_tracelog

            body_dict = json.loads(body.decode('utf-8'), object_pairs_hook=OrderedDict)
            msg_type = body_dict['_type']

            logger.info(
                '[%s] Checking correlated request/response for message %s'
                % (sys._getframe().f_code.co_name, props.message_id))

            ch.basic_ack(delivery_tag=method.delivery_tag)

            if msg_type == 'testingtool.terminate':
                ch.stop_consuming()
                return

            if msg_type in events_to_ignore:
                # forget about these.. we are checking services and services reply only
                return

            if '.service.reply' in method.routing_key:
                if props.correlation_id in services_mid_backlog:
                    services_mid_backlog.remove(props.correlation_id)
                    services_events_tracelog.append((msg_type, props.correlation_id))
                else:
                    assert False, 'got a reply but theres no request in the backlog'

            elif '.service' in method.routing_key:
                services_mid_backlog.append(props.correlation_id)
                services_events_tracelog.append((msg_type, props.correlation_id))

            else:
                assert False, 'error! unexpected routing key: %s or event: %s' % (method.routing_key, msg_type)

            logging.info("[%s] current backlog: %s . history: %s"
                         % (
                             sys._getframe().f_code.co_name,
                             services_mid_backlog,
                             services_events_tracelog
                         )
                         )

        # CORRELATION VALIDATOR BOUND TO SERVICES & REPLIES QUEUE
        services_queue_name = 'services_queue@%s' % COMPONENT_ID
        self.channel.queue_delete(queue=services_queue_name)
        self.channel.queue_declare(queue=services_queue_name, auto_delete=True)

        # get all services messages and their replies
        self.channel.queue_bind(exchange=AMQP_EXCHANGE, queue=services_queue_name, routing_key='#.service')
        self.channel.queue_bind(exchange=AMQP_EXCHANGE, queue=services_queue_name, routing_key='#.service.reply')
        self.channel.basic_qos(prefetch_count=1)

        # for getting the terminate signal
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=services_queue_name,
                                routing_key=MsgTestingToolTerminate.routing_key)

        # for checking that for every request we get a reply
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(check_for_correlated_request_reply, queue=services_queue_name)

        # prepare the message generator
        messages = []  # list of messages to send
        messages += service_api_calls
        messages.append(MsgTestingToolTerminate())  # message that triggers stop_generator_signal

        thread_msg_gen = MessageGenerator(
            amqp_url=AMQP_URL,
            amqp_exchange=AMQP_EXCHANGE,
            messages_list=messages,
            wait_time_between_pubs=MESSAGES_WAIT_INTERVAL
        )
        logger.debug("[%s] Starting Message Generator thread " % sys._getframe().f_code.co_name)

        publish_message(self.conn, MsgSessionConfiguration(
            configuration=default_configuration))  # this prepares the FSM of the coordinator
        publish_message(self.conn, MsgTestSuiteStart())  # this prepares the FSM of the coordinator
        time.sleep(10)  # wait for the testing tool to enter test suite ready state

        try:
            thread_msg_gen.start()
            self.channel.start_consuming()
            if len(services_mid_backlog) > 0:
                assert False, 'A least one of the services request was not answered. backlog: %s. History: %s' \
                              % (
                                  services_mid_backlog,
                                  services_events_tracelog
                              )
        except Exception as e:
            thread_msg_gen.stop()
            assert False, str(e)


# # # # # # AUXILIARY METHODS # # # # # # #


def import_env_vars():
    global AMQP_EXCHANGE
    global AMQP_URL

    try:
        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
    except KeyError as e:
        AMQP_EXCHANGE = "amq.topic"

    try:
        AMQP_URL = str(os.environ['AMQP_URL'])
        p = urlparse(AMQP_URL)
        AMQP_USER = p.username
        AMQP_SERVER = p.hostname
        logger.info(
            "Env variables imported for AMQP connection, User: {0} @ Server: {1} ".format(AMQP_USER, AMQP_SERVER)
        )
    except KeyError as e:
        logger.error('Cannot retrieve environment variables for AMQP connection. Loading defaults..')
        # load default values
        AMQP_URL = "amqp://{0}:{1}@{2}/{3}".format("guest", "guest", "localhost", "/")

    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

    connection.close()


def stop_generator():
    global stop_generator_signal
    logger.debug("The test is finished!")
    stop_generator_signal = True


def check_for_bus_error(ch, method, props, body):
    """
    If function was called then it means an error log was found in the bus.
    """

    logger.info('[%s] Checking if is error, message %s' % (sys._getframe().f_code.co_name, props.message_id))

    try:
        msg = Message.from_json(body)
        if isinstance(msg, MsgTestingToolTerminate):
            ch.stop_consuming()
            return
    except:
        pass

    list_of_audited_components = [
        'tat',
        'test_coordinator',
        'packer_router',
        'sniffer',
        'dissector'
        'session',
        # TODO add agent_TT messages
    ]
    r_key = method.routing_key
    logger.info('[%s] Auditing: %s' % (sys._getframe().f_code.co_name, r_key))

    for c in list_of_audited_components:
        if c in r_key:
            err = 'audited component %s pushed an error into the bus. messsage: %s' % (c, body)
            logger.error(err)
            raise Exception(err)


def validate_message(ch, method, props, body):
    global message_count
    tab = '\t'
    # obj hook so json.loads respects the order of the fields sent -just for visualization purposeses-
    req_body_dict = json.loads(body.decode('utf-8'), object_pairs_hook=OrderedDict)
    ch.basic_ack(delivery_tag=method.delivery_tag)
    message_count += 1

    logger.info('[%s] Checking valid format for message %s' % (sys._getframe().f_code.co_name, props.message_id))

    print('\n' + tab + '* * * * * * MESSAGE SNIFFED by INSPECTOR (%s) * * * * * * *' % message_count)
    print(tab + "TIME: %s" % datetime.datetime.time(datetime.datetime.now()))
    print(tab + "ROUTING_KEY: %s" % method.routing_key)
    print(tab + "MESSAGE ID: %s" % props.message_id)
    if hasattr(props, 'correlation_id'):
        print(tab + "CORRELATION ID: %s" % props.correlation_id)
    print(tab + 'EVENT %s' % (req_body_dict['_type']))
    print(tab + '* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * \n')

    if props.content_type != "application/json":
        print(tab + '* * * * * * API VALIDATION ERROR * * * * * * * ')
        print(tab + "props.content_type : " + str(props.content_type))
        print(tab + "application/json was expected")
        print(tab + '* * * * * * * * * * * * * * * * * * * * * * * * *  \n')
        raise Exception

    if '_type' not in req_body_dict.keys():
        print(tab + '* * * * * * API VALIDATION ERROR * * * * * * * ')
        print(tab + "no < _type > field found")
        print(tab + '* * * * * * * * * * * * * * * * * * * * * * * * *  \n')
        raise Exception

    # lets check messages against the messaging library
    list_of_messages_to_check = list(message_types_dict.keys())
    if req_body_dict['_type'] in list_of_messages_to_check:
        m = Message.from_json(body)
        try:
            if isinstance(m, MsgTestingToolTerminate):
                ch.stop_consuming()
                stop_generator()
            else:
                logger.debug(repr(m))
        except NonCompliantMessageFormatError as e:
            print(tab + '* * * * * * API VALIDATION ERROR * * * * * * * ')
            print(tab + "AMQP MESSAGE LIBRARY COULD PROCESS JSON MESSAGE")
            print(tab + '* * * * * * * * * * * * * * * * * * * * * * * * *  \n')
            raise NonCompliantMessageFormatError("AMQP MESSAGE LIBRARY COULD PROCESS JSON MESSAGE")
