# -*- coding: utf-8 -*-
# !/usr/bin/env python3

from ioppytest import AMQP_URL, AMQP_EXCHANGE
from ioppytest.utils.messages import *
from ioppytest.utils.event_bus_utils import publish_message, AmqpListener
from automated_IUTs.automation import UserMock

from urllib.parse import urlparse
import logging
import unittest
import pika
import sys
import os

COMPONENT_ID = 'fake_session'
THREAD_JOIN_TIMEOUT = 300

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

logging.getLogger('pika').setLevel(logging.INFO)

# queue which tracks all non answered services requests
events_sniffed_on_bus_dict = {}  # the dict allows us to index last received messages of each type
event_types_sniffed_on_bus_list = []  # the list allows us to monitor the order of events

"""
EXECUTE AS:
    python3 -m pytest -p no:cacheprovider tests/complete_integration_test.py -vvv

PRE-CONDITIONS:
- Export AMQP_URL in the running environment
- Have CoAP testing tool running & listening to the bus
- Have an automated-iut coap client and an automated-iut coap server running & listening to the bus
"""


class CompleteFunctionalCoapSessionTests(unittest.TestCase):
    def setUp(self):
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

    def tearDown(self):
        self.connection.close()

    def test_complete_interop_test_cycle(self):
        global event_types_sniffed_on_bus_list
        global events_sniffed_on_bus_dict
        global THREAD_JOIN_TIMEOUT

        tc_list = ['TD_COAP_CORE_01']  # the rest of the testcases are going to be skipped

        # thread
        u = UserMock(
            iut_testcases=tc_list
        )

        # thread
        e = AmqpListener(
            amqp_url=AMQP_URL,
            amqp_exchange=AMQP_EXCHANGE,
            callback=run_checks_on_message_received,
            topics=['#'],
            use_message_typing=True
        )

        u.setName(u.__class__.__name__)
        e.setName(u.__class__.__name__)

        try:
            u.start()
            e.start()
            publish_message(
                connection=self.connection,
                message=MsgSessionConfiguration(
                    configuration={
                        "testsuite.testcases": [
                            "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
                            "http://doc.f-interop.eu/tests/TD_COAP_CORE_02",
                            "http://doc.f-interop.eu/tests/TD_COAP_CORE_03",
                        ]
                    }
                )  # from TC1 to TC3
            )

            # waits THREAD_JOIN_TIMEOUT for the session to terminate
            u.join(THREAD_JOIN_TIMEOUT)
            e.join(THREAD_JOIN_TIMEOUT)

        except Exception as e:
            self.fail("Exception encountered %s" % e)

        finally:
            if u.is_alive():
                u.stop()

            if e.is_alive():
                e.stop()

            logging.info("Events sniffed in bus: %s" % event_types_sniffed_on_bus_list)

            assert MsgTestSuiteReport in event_types_sniffed_on_bus_list, "Testing tool didnt emit any report"
            assert MsgTestSuiteReport in events_sniffed_on_bus_dict, "Testing tool didnt emit any report"

            logging.info('SUCCESS! TT + additional resources executed the a complete interop test :D ')
            logging.info('report: %s' % repr(events_sniffed_on_bus_dict[MsgTestSuiteReport]))


def run_checks_on_message_received(message: Message):
    assert message
    logger.info('[%s]: %s' % (sys._getframe().f_code.co_name, repr(message)[:70]))
    update_events_seen_on_bus_list(message)
    check_if_message_is_an_error_message(message)
    publish_terminate_signal_on_report_received(message)
    check_api_version(message)


# # # # # # AUXILIARY METHODS # # # # # # #

def publish_terminate_signal_on_report_received(message: Message):
    if isinstance(message, MsgTestSuiteReport):
        logger.info('Got final report %s' % repr(message))
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        publish_message(
            connection,
            MsgTestingToolTerminate(description="Received report, functional test finished..")
        )


def check_if_message_is_an_error_message(message: Message):
    logger.info('[%s]: %s' % (sys._getframe().f_code.co_name, type(message)))
    assert 'error' not in message.routing_key, 'Got an error %s' % repr(message)
    assert not isinstance(message, MsgErrorReply), 'Got an error reply %s' % repr(message)
    assert not (isinstance(message, MsgReply) and message.ok == False), 'Got a reply with a NOK reponse %s' % repr(
        message)


def update_events_seen_on_bus_list(message: Message):
    global event_types_sniffed_on_bus_list
    global events_sniffed_on_bus_dict
    events_sniffed_on_bus_dict[type(message)] = message
    event_types_sniffed_on_bus_list.append(type(message))


def check_api_version(message: Message):
    try:
        assert message._api_version, 'Message didnt enclude API version metadata'
    except:
        logger.warning('Message didnt enclude API version metadata')
        return

    assert message._api_version.startswith("1"), "Running incompatible version of API"
