# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import sys
import pika
import pprint
import logging
import unittest
import os

from messages import *
from ioppytest import AMQP_URL, AMQP_EXCHANGE
from event_bus_utils import publish_message, AmqpListener, amqp_request
from automated_IUTs.automation import UserMock

from tests import (
    check_if_message_is_an_error_message,
    publish_terminate_signal_on_report_received,
    check_api_version,
    reply_to_ui_configuration_request_stub,
    connect_and_publish_message,
    default_configuration,
    log_all_received_messages,
    MAX_LINE_LENGTH
)

"""
Testing Tool tested as a black box, it uses the event bus API as stimulation and evaluation point.
Evaluates a normal test cycle with real automated IUTs. 

EXECUTE AS:
    
    python3 -m pytest -p no:cacheprovider tests/integration_test__full_coap_interop_session.py -vvv

for more verbose output:
    python3 -m unittest tests/integration_test__full_coap_interop_session.py -vvv

PRE-CONDITIONS:
- Export AMQP_URL in the running environment
- Have CoAP testing tool running & listening to the bus
- Have an automated-iut coap client and an automated-iut coap server running & listening to the bus
"""

COMPONENT_ID = 'fake_session'
SESSION_TIMEOUT = 300
EXECUTE_ALL_TESTS = os.environ.get('CI', 'False') == 'True'
COAP_CLIENT_IS_AUTOMATED = os.environ.get('COAP_CLIENT_IS_AUTOMATED', 'True') == 'True'
COAP_SERVER_IS_AUTOMATED = os.environ.get('COAP_SERVER_IS_AUTOMATED', 'True') == 'True'

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

logging.getLogger('pika').setLevel(logging.WARNING)

# queue which tracks all non answered services requests
events_sniffed_on_bus_dict = {}  # the dict allows us to index last received messages of each type
event_messages_sniffed_on_bus_list = []  # the list of messages seen on the bus


class CompleteFunctionalCoapSessionTests(unittest.TestCase):
    global event_messages_sniffed_on_bus_list
    global events_sniffed_on_bus_dict
    global SESSION_TIMEOUT

    def setUp(self):
        self.got_at_least_one_passed_tc = False
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

    def tearDown(self):
        self.connection.close()
        log_all_received_messages(event_messages_sniffed_on_bus_list)

    def test_complete_interop_test_cycle(self):
        if EXECUTE_ALL_TESTS:
            tc_list = None
            logger.info("Detected CI environment. Executing all tests")
        else:
            tc_list = [
                'TD_COAP_CORE_01',
                'TD_COAP_CORE_02',
                'TD_COAP_CORE_03'
            ]  # the rest of the testcases are going to be skipped

        # thread
        msg_consumer = AmqpListener(
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
        non_automated_iuts = []
        if not COAP_CLIENT_IS_AUTOMATED:
            non_automated_iuts.append('coap_client')
        if not COAP_SERVER_IS_AUTOMATED:
            non_automated_iuts.append('coap_server')
        user_stub = UserMock(
            iut_testcases=tc_list,
            iut_to_mock_verifications_for=non_automated_iuts
        )

        msg_consumer.setName('msg_consumer')
        user_stub.setName('user_stub')
        ui_stub.setName('ui_stub')

        threads = [
            user_stub,
            msg_consumer,
            ui_stub,
        ]

        try:
            for th in threads:
                th.start()

            publish_message(
                self.connection,
                MsgSessionConfiguration(configuration=default_configuration),
            )  # configures test suite, this triggers start of userMock also

            self.connection.close()

            t = 0
            WAIT_PERIOD = 1  # seconds
            # wait until we get MsgTestSuiteReport
            while t < SESSION_TIMEOUT and MsgTestSuiteReport not in events_sniffed_on_bus_dict:
                time.sleep(WAIT_PERIOD)
                if t == SESSION_TIMEOUT/2:
                    logging.info("reached half of the expected time for the test execution, is everything alright?")
                    log_all_received_messages(event_list=event_messages_sniffed_on_bus_list)
                t += WAIT_PERIOD

            connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

            if t >= SESSION_TIMEOUT:
                r = amqp_request(connection, MsgTestSuiteGetStatus(), COMPONENT_ID)
                logging.warning('Test TIMED-OUT! Test suite status:\n%s' % pprint.pformat(r.to_dict()))

            if MsgTestingToolTerminate not in events_sniffed_on_bus_dict:
                logging.warning('Never received TERMINATE signal')
                publish_message(
                    connection,
                    MsgTestingToolTerminate(description="Triggering TERMINATION.")
                )

            time.sleep(10)  # so threads process TERMINATE signal
            connection.close()
            logging.info("Checking all threads have stopped..")
            try:
                for th in threads:
                    if th.is_alive():
                        logging.warning("Thread %s didn't stop with the TERMINATE signal" % th.name)
                        th.stop()
            except Exception as e:  # I dont want this to make my tests fail
                pass

            logging.info("All threads have stopped..")

        except Exception as e:
            self.fail("Exception encountered:\n%s" % e)

        finally:

            assert MsgTestSuiteReport in events_sniffed_on_bus_dict, \
                "Testing tool didn't emit any report, list of events:\n%s" % pprint.pformat(
                    object=event_messages_sniffed_on_bus_list,
                    indent=4
                )

            logging.info('Got TestSuiteReport. Test suite completely executed')

            for tc_report in events_sniffed_on_bus_dict[MsgTestSuiteReport].tc_results:
                logging.info('\t%s' % pprint.pformat(object=tc_report, indent=4))

                if 'verdict' in tc_report and str(tc_report['verdict']).lower() == 'pass':
                    self.got_at_least_one_passed_tc = True

            if self.got_at_least_one_passed_tc:
                logging.info('Got at least one PASS verdict :)')
            else:
                logging.warning('No PASS verdict found in the session results report :(')


def run_checks_on_message_received(message: Message):
    global event_messages_sniffed_on_bus_list
    global events_sniffed_on_bus_dict
    assert message

    logging.debug('[%s]: %s' % (sys._getframe().f_code.co_name, repr(message)[:MAX_LINE_LENGTH]))
    update_events_seen_on_bus_list(message)
    publish_terminate_signal_on_report_received(message)
    #check_if_message_is_an_error_message(message)
    check_api_version(message)


def update_events_seen_on_bus_list(message: Message):
    global event_messages_sniffed_on_bus_list
    global events_sniffed_on_bus_dict

    events_sniffed_on_bus_dict[type(message)] = message
    event_messages_sniffed_on_bus_list.append(message)
