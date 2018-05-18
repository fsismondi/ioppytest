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
                   connect_and_publish_message,
                   log_all_received_messages,
                   MAX_LINE_LENGTH)

"""
Testing Tool tested as a black box, it uses the event bus API as stimulation and evaluation point.
Evaluates a normal test cycle with real automated IUTs. 

EXECUTE AS:
python3 -m pytest -p no:cacheprovider tests/complete_integration_test.py -vvv

PRE-CONDITIONS:
- Export AMQP_URL in the running environment
- Have CoAP testing tool running & listening to the bus
- Have an automated-iut coap client and an automated-iut coap server running & listening to the bus
"""

COMPONENT_ID = 'fake_session'
SESSION_TIMEOUT = 600

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

logging.getLogger('pika').setLevel(logging.WARNING)

# queue which tracks all non answered services requests
events_sniffed_on_bus_dict = {}  # the dict allows us to index last received messages of each type
event_messages_sniffed_on_bus_list = []  # the list of messages seen on the bus


class CompleteFunctionalCoapSessionTests(unittest.TestCase):
    def setUp(self):
        self.got_at_least_one_passed_tc = False
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

    def tearDown(self):
        self.connection.close()
        log_all_received_messages(event_messages_sniffed_on_bus_list)

    def test_complete_interop_test_cycle(self):
        global event_messages_sniffed_on_bus_list
        global events_sniffed_on_bus_dict
        global SESSION_TIMEOUT

        tc_list = [
            'TD_COAP_CORE_01',
            'TD_COAP_CORE_02',
            'TD_COAP_CORE_03'
        ]  # the rest of the testcases are going to be skipped

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

        msg_validator.setName('msg_validator')
        user_stub.setName('user_stub')
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

            t = 0
            # wait until we get MsgTestSuiteReport
            while t < SESSION_TIMEOUT and MsgTestSuiteReport not in events_sniffed_on_bus_dict:
                time.sleep(1)
                t += 1

        except Exception as e:
            self.fail("Exception encountered %s" % e)

        finally:
            for th in threads:
                if th.is_alive():
                    logger.warning("Thread %s didnt stop" % th.name)
                    th.stop()

            assert MsgTestSuiteReport in events_sniffed_on_bus_dict, "Testing tool didnt emit any report"
            logging.info('Got TestSuiteReport. Test suite completely executed')

            for tc_report in events_sniffed_on_bus_dict[MsgTestSuiteReport].tc_results:
                logging.info('\t%s' % tc_report)
                if 'verdict' in tc_report and str(tc_report['verdict']).lower() == 'pass':
                    self.got_at_least_one_passed_tc = True

            if self.got_at_least_one_passed_tc:
                logging.info('Got at least one PASS verdict')
            else:
                logging.warning('(!)No PASS verdict found in the session results report')


def run_checks_on_message_received(message: Message):
    assert message
    logging.debug('[%s]: %s' % (sys._getframe().f_code.co_name, repr(message)[:MAX_LINE_LENGTH]))
    update_events_seen_on_bus_list(message)
    check_if_message_is_an_error_message(message)
    publish_terminate_signal_on_report_received(message)
    check_api_version(message)


def update_events_seen_on_bus_list(message: Message):
    global event_messages_sniffed_on_bus_list
    global events_sniffed_on_bus_dict
    events_sniffed_on_bus_dict[type(message)] = message
    event_messages_sniffed_on_bus_list.append(message)
