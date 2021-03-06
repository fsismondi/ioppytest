# -*- coding: utf-8 -*-
# !/usr/bin/env python3

from urllib.parse import urlparse
import logging

import unittest
import pika
import sys
import time
import os
import threading
import datetime

from ioppytest import AMQP_URL, AMQP_EXCHANGE
from messages import *
from event_bus_utils import publish_message, AmqpListener

from tests import MessageGenerator, default_configuration
from tests.pcap_base64_examples import *

from tests import (check_if_message_is_an_error_message,
                   publish_terminate_signal_on_report_received,
                   check_api_version,
                   reply_to_ui_configuration_request_stub,
                   log_all_received_messages,
                   MAX_LINE_LENGTH,
                   )

"""
Testing Tool tested as a black box, it uses the event bus API as stimulation and evaluation point.

EXECUTE AS:
python3 -m pytest -p no:cacheprovider tests/black_box_test___test_testing_tool_event_bus_api.py -vvv
or
python3 -m unittest tests/black_box_test___test_testing_tool_event_bus_api.py -vvv

PRE-CONDITIONS:
- Export AMQP_URL in the running environment
- Have CoAP testing tool running & listening to the bus
"""

# queue which tracks all non answered services requests
events_sniffed_on_bus_dict = {}  # the dict allows us to index last received messages of each type
event_messages_sniffed_on_bus_list = []  # list of all events in the bus

COMPONENT_ID = 'fake_session'
THREAD_JOIN_TIMEOUT = 90

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

logging.getLogger('pika').setLevel(logging.WARNING)

# this sequence of messages will simulate the user inputs, and exercise the test coordinator's FSM
user_sequence = [
    MsgAgentTunStarted(
        name="someAgentName1",
        ipv6_prefix="bbbb",
        ipv6_host="1",
    ),
    MsgAgentTunStarted(
        name="someAgentName2",
        ipv6_prefix="bbbb",
        ipv6_host="2",
    ),

    MsgTestSuiteGetStatus(),
    MsgTestCaseSkip(testcase_id='TD_COAP_CORE_02'),
    MsgTestSuiteGetStatus(),
    MsgTestCaseSkip(testcase_id='TD_COAP_CORE_03'),
    MsgTestSuiteGetStatus(),
    MsgTestCaseStart(),  # execute TC1  ( w/ no IUT in the bus )
    MsgTestSuiteGetStatus(),
    MsgStepStimuliExecuted(),
    MsgTestSuiteGetStatus(),
    MsgStepVerifyExecuted(
        verify_response=False,
        description='User indicates that IUT didnt behave as expected '),
    MsgTestSuiteGetStatus(),
    MsgTestSuiteGetStatus(),  # at this point we should see a TC verdict
    MsgTestCaseRestart(),
    MsgTestSuiteGetStatus(),
    MsgTestSuiteAbort(),
    MsgTestSuiteGetStatus(),
]

# this sequence of messages will test testing tool components
service_api_calls = [

    # TAT calls
    MsgTestSuiteGetStatus(),
    MsgTestSuiteGetTestCases(),
    MsgInteropTestCaseAnalyze(
        testcase_id="TD_COAP_CORE_01",
        testcase_ref="http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
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
    MsgTestSuiteGetStatus(),
    MsgPacketSniffedRaw(),  # send a data message (should be a ping)
    MsgPacketSniffedRaw(),  # send a data message (should be a ping)
    MsgPacketSniffedRaw(),  # send a data message (should be a ping)
    MsgPacketSniffedRaw(),  # send a data message (should be a ping)
    MsgPacketSniffedRaw(),  # send a data message (should be a ping)
    MsgPacketSniffedRaw(),  # send a data message (should be a ping)
    MsgPacketSniffedRaw(),  # send a data message (should be a ping)
    MsgPacketSniffedRaw(),  # send a data message (should be a ping)
    MsgTestSuiteGetStatus(),
    MsgSniffingStop(),
    MsgSniffingGetCapture(tescase_id='TD_COAP_CORE_01'),
    MsgSniffingGetCaptureLast(),

    # Dissector calls
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

    def setUp(self):
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

    def tearDown(self):
        self.connection.close()
        # print messages
        log_all_received_messages(event_messages_sniffed_on_bus_list)

    def test_amqp_api_smoke_tests(self):
        """
        This basically checks that the testing tool doesnt crash while user is pushing message inputs into to the bus.
        We check for:
        - log errors in the bus
        - malformed messages in the bus
        - every request has a reply

        """

        # prepare the message generator
        messages = []  # list of messages to send
        messages += user_sequence
        messages += service_api_calls
        messages.append(MsgTestingToolTerminate())  # message that triggers stop_generator_signal

        # thread
        thread_msg_gen = MessageGenerator(
            amqp_url=AMQP_URL,
            amqp_exchange=AMQP_EXCHANGE,
            messages_list=messages,
            # att (!) some test run cycles of more that 100 messages, so this factor will change enourmosuly the time it
            # takes to complete a test
            wait_time_between_pubs=0.25
        )

        # thread
        thread_msg_listener = AmqpListener(
            amqp_url=AMQP_URL,
            amqp_exchange=AMQP_EXCHANGE,
            callback=run_checks_on_message_received,
            topics=['#'],
            use_message_typing=True
        )

        threads = [thread_msg_listener, thread_msg_gen]

        for th in threads:
            th.setName(th.__class__.__name__)

        time.sleep(15)  # wait for the testing tool to enter test suite ready state

        try:
            for th in threads:
                th.start()

            publish_message(
                self.connection,
                MsgSessionConfiguration(configuration=default_configuration),
            )  # configures test suite

            time.sleep(1)

            publish_message(
                self.connection,
                MsgTestSuiteStart()
            )  # this starts test suite's FS

            self.connection.close()

            # waits THREAD_JOIN_TIMEOUT for the session to terminate
            for th in threads:
                th.join(THREAD_JOIN_TIMEOUT)

        except Exception as e:
            self.fail("Exception encountered %s" % e)

        finally:
            for th in threads:
                if th.is_alive():
                    th.stop()
                    logger.warning("Thread %s didnt stop" % th.name)

            # finally checks
            check_request_with_no_correlation_id(event_messages_sniffed_on_bus_list)
            check_every_request_has_a_reply(event_messages_sniffed_on_bus_list)


def run_checks_on_message_received(message: Message):
    assert message
    logging.debug('[%s]: %s' % (sys._getframe().f_code.co_name, repr(message)[:MAX_LINE_LENGTH]))
    update_events_seen_on_bus_list(message=message)
    check_if_message_is_an_error_message(message=message, fail_on_reply_nok=False)
    check_api_version(message=message)


# # # # # # AUXILIARY METHODS # # # # # # #


def stop_generator():
    global stop_generator_signal
    logger.debug("The test is finished!")
    stop_generator_signal = True


def check_request_with_no_correlation_id(events_tracelog):
    non_compiant = []
    for ev in events_tracelog:
        if ".request" in ev.routing_key:
            if not hasattr(ev, 'correlation_id'):
                non_compiant.append(ev)

    if len(non_compiant) > 0:
        m = "Request with no correlation id: %s" % len(non_compiant)
        logging.warning(m)
        for i in non_compiant:
            logging.warning("Request with no correlation id: %s" % repr(i)[:MAX_LINE_LENGTH])
        raise Exception(m)


def check_every_request_has_a_reply(events_tracelog):
    for ev in events_tracelog:
        if ".request" in ev.routing_key:
            corr_id = ev.correlation_id
            found_correlated_message = False
            for ev_request_finder in events_tracelog:
                if ".reply" in ev_request_finder.routing_key and corr_id == ev_request_finder.correlation_id:
                    found_correlated_message = True
                    logging.info('[%s]: found request and its reply %s / %s ' % (
                        sys._getframe().f_code.co_name,
                        repr(ev)[:MAX_LINE_LENGTH],
                        repr(ev_request_finder)[:MAX_LINE_LENGTH]
                    ))
                    break

            if not found_correlated_message:
                raise Exception("No correlated message reply for request %s" % repr(ev))

    logger.info("checked run for %s messages from the messages backlog" % len(events_tracelog))

    if len(events_tracelog) == 0:
        raise Exception("This is not right.. we got ZERO messages in the backlog")


def update_events_seen_on_bus_list(message: Message):
    global event_messages_sniffed_on_bus_list
    global events_sniffed_on_bus_dict
    events_sniffed_on_bus_dict[type(message)] = message
    event_messages_sniffed_on_bus_list.append(message)
