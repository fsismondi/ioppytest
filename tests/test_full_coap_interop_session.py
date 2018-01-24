# -*- coding: utf-8 -*-
# !/usr/bin/env python3


import os
import sys
import pika
import logging
import unittest
from urllib.parse import urlparse

from ioppytest import AMQP_URL, AMQP_EXCHANGE
from ioppytest.utils.messages import *
from ioppytest.utils.event_bus_utils import publish_message, AmqpListener
from automated_IUTs.automation import UserMock

from tests import (check_if_message_is_an_error_message,
                   publish_terminate_signal_on_report_received,
                   check_api_version,
                   reply_to_ui_configuration_request_stub,
                   connect_and_publish_message)

COMPONENT_ID = 'fake_session'
THREAD_JOIN_TIMEOUT = 120
MAX_LINE_LENGTH = 100

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

logging.getLogger('pika').setLevel(logging.INFO)

# queue which tracks all non answered services requests
events_sniffed_on_bus_dict = {}  # the dict allows us to index last received messages of each type
event_types_sniffed_on_bus_list = []  # the list allows us to monitor the order of events


class CompleteFunctionalCoapSessionTests(unittest.TestCase):
    """
    Testing Tool tested as a black box, it uses the event bus API as stimulation and evaluation point.

    EXECUTE AS:
    python3 -m pytest -p no:cacheprovider tests/complete_integration_test.py -vvv

    PRE-CONDITIONS:
    - Export AMQP_URL in the running environment
    - Have CoAP testing tool running & listening to the bus
    - Have an automated-iut coap client and an automated-iut coap server running & listening to the bus
    """

    def setUp(self):
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

    def tearDown(self):
        self.connection.close()
        log_all_received_messages(event_types_sniffed_on_bus_list)

    def test_complete_interop_test_cycle(self):
        global event_types_sniffed_on_bus_list
        global events_sniffed_on_bus_dict
        global THREAD_JOIN_TIMEOUT

        tc_list = ['TD_COAP_CORE_01']  # the rest of the testcases are going to be skipped

        # thread
        msg_validator = AmqpListener(
            amqp_url=AMQP_URL,
            amqp_exchange=AMQP_EXCHANGE,
            callback=run_checks_on_message_received,
            topics=['#'],
            use_message_typing=True
        )

        # thread
        ui_stub = AmqpListener(
            amqp_url=AMQP_URL,
            amqp_exchange=AMQP_EXCHANGE,
            callback=reply_to_ui_configuration_request_stub,
            topics=[
                MsgUiRequestSessionConfiguration.routing_key,
                MsgTestingToolTerminate.routing_key,
            ],
            use_message_typing=True
        )

        # thread
        user_stub = UserMock(
            iut_testcases=tc_list
        )

        user_stub.setName('user_mock')
        msg_validator.setName('message_validator')
        ui_stub.setName('ui_stub')

        threads = [
            user_stub,
            msg_validator,
            ui_stub,
        ]

        try:
            self.connection.close()

            for th in threads:
                th.start()

            # waits THREAD_JOIN_TIMEOUT for the session to terminate
            # be careful Jenkins scripts have a timeout for jobs to finish execution
            for th in threads:
                th.join(THREAD_JOIN_TIMEOUT)

        except Exception as e:
            self.fail("Exception encountered %s" % e)

        finally:
            for th in threads:
                if th.is_alive():
                    th.stop()
                    logger.warning("Thread %s didnt stop" % th.name)

            log_all_received_messages(event_types_sniffed_on_bus_list)

            assert MsgTestSuiteReport in event_types_sniffed_on_bus_list, "Testing tool didnt emit any report"
            assert MsgTestSuiteReport in events_sniffed_on_bus_dict, "Testing tool didnt emit any report"

            logging.info('SUCCESS! TT + additional resources executed the a complete interop test :D ')
            logging.info('report: %s' % repr(events_sniffed_on_bus_dict[MsgTestSuiteReport]))


def log_all_received_messages(event_types_sniffed_on_bus_list:list):
    logging.info("Events sniffed in bus: %s" % len(event_types_sniffed_on_bus_list))
    i = 0
    for ev in event_types_sniffed_on_bus_list:
        i += 1
        logging.info("Event sniffed (%s): %s" % (i, repr(ev)[:MAX_LINE_LENGTH]))


def run_checks_on_message_received(message: Message):
    assert message
    logging.info('[%s]: %s' % (sys._getframe().f_code.co_name, repr(message)[:MAX_LINE_LENGTH]))
    update_events_seen_on_bus_list(message)
    check_if_message_is_an_error_message(message)
    publish_terminate_signal_on_report_received(message)
    check_api_version(message)


def update_events_seen_on_bus_list(message: Message):
    global event_types_sniffed_on_bus_list
    global events_sniffed_on_bus_dict
    events_sniffed_on_bus_dict[type(message)] = message
    event_types_sniffed_on_bus_list.append(type(message))
