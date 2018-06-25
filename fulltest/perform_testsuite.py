# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import pika
import pprint
import os

from fulltest.messagelogger import MessageLogger, log_all_received_messages
from fulltest.ui_stub import default_configuration, UIStub
from ioppytest import AMQP_URL, AMQP_EXCHANGE
from ioppytest.utils.messages import *
from ioppytest.utils.event_bus_utils import publish_message, amqp_request, AmqpSynchCallTimeoutError
from automated_IUTs.automation import UserMock

"""
Testing Tool tested as a black box, it uses the event bus API as stimulation and evaluation point.
Evaluates a normal test cycle with real automated IUTs. 

EXECUTE AS:

    python3 -m pytest -p no:cacheprovider tests/complete_integration_test.py -vvv

for more verbose output:
    python3 -m unittest tests/test_full_coap_interop_session.py -vvv

PRE-CONDITIONS:
- Export AMQP_URL in the running environment
- Have CoAP testing tool running & listening to the bus
- Have an automated-iut coap client and an automated-iut coap server running & listening to the bus
"""

COMPONENT_ID = 'perform_testsuite'
SESSION_TIMEOUT = 300
EXECUTE_ALL_TESTS = os.environ.get('CI', 'False') == 'True'
COAP_CLIENT_IS_AUTOMATED = os.environ.get('COAP_CLIENT_IS_AUTOMATED', 'True') == 'True'
COAP_SERVER_IS_AUTOMATED = os.environ.get('COAP_SERVER_IS_AUTOMATED', 'True') == 'True'

logging.basicConfig(format='%(levelname)s [%(name)s]:%(message)s', level=logging.DEBUG)
logging.getLogger('pika').setLevel(logging.WARNING)
logging.getLogger('ioppytest.utils.event_bus_utils').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class PerformFullTest(object):

    def __init__(self):
        self.error_state = False

        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

        if EXECUTE_ALL_TESTS:
            self.tc_list = ['TD_COAP_CORE_%02d' % i for i in range(1, 10)]
            logger.info("Detected CI environment. Executing all tests supported by both Californium and CoAPthon")
        else:
            self.tc_list = [
                'TD_COAP_CORE_01',
                'TD_COAP_CORE_02',
                'TD_COAP_CORE_03'
            ]  # the rest of the testcases are going to be skipped
            logger.info("Executing 3 first tests")
        self.non_automated_iuts = []
        if not COAP_CLIENT_IS_AUTOMATED:
            self.non_automated_iuts.append('coap_client')
        if not COAP_SERVER_IS_AUTOMATED:
            self.non_automated_iuts.append('coap_server')

        self.msglogger = MessageLogger(AMQP_URL, AMQP_EXCHANGE)

    def stop(self):
        self.connection.close()

        if self.error_state:
            log_all_received_messages(self.msglogger.messages_list)

    def run(self):

        # start the various threads

        # thread
        ui_stub = UIStub(AMQP_URL, AMQP_EXCHANGE)

        # thread
        user_stub = UserMock(
            iut_testcases=self.tc_list,
            iut_to_mock_verifications_for=self.non_automated_iuts
        )

        self.msglogger.setName('msg_validator')
        user_stub.setName('user_stub')
        ui_stub.setName('ui_stub')

        threads = [
            user_stub,
            self.msglogger,
            ui_stub,
        ]

        try:
            for th in threads:
                th.start()

            self.check_session_start_status()

            logger.info("Sending session configuration to start tests")
            publish_message(
                self.connection,
                MsgSessionConfiguration(configuration=default_configuration),
            )  # configures test suite, this triggers start of userMock also

            t = 0
            # wait until we get MsgTestSuiteReport
            while t < SESSION_TIMEOUT and MsgTestSuiteReport not in self.msglogger.messages_by_type_dict:
                time.sleep(5)
                t += 5

                if t % 15 == 0:
                    self.get_status()

            if t >= SESSION_TIMEOUT:
                r = amqp_request(self.connection, MsgTestSuiteGetStatus(), COMPONENT_ID)
                logger.warning('Test TIMED-OUT! Test suite status:\n%s' % pprint.pformat(r.to_dict()))
            else:
                assert MsgTestSuiteReport in self.msglogger.messages_by_type_dict

                # we can now terminate the session
                publish_message(
                    self.connection,
                    MsgTestingToolTerminate(description="Received report, functional test finished..")
                )

                time.sleep(2)

        except Exception as e:
            self.error_state = True
            logger.error("Exception encountered in PerformTestsuite:\n%s", e)

        finally:
            if MsgTestingToolTerminate not in self.msglogger.messages_by_type_dict:
                logger.warning('Never received TERMINATE signal')
                publish_message(
                    self.connection,
                    MsgTestingToolTerminate(description="Integration test of CoAP interop test: sth went wrong :/")
                )

            time.sleep(10)  # so threads process TERMINATE signal

            try:
                for th in threads:
                    if th.is_alive():
                        logger.warning("Thread %s didn't stop" % th.name)
                        th.stop()
            except Exception as e:  # i dont want this to make my tests fail
                logger.warning('Exception thrown while stopping threads:\n%s' % e)

    def check_session_start_status(self):
        retries_left = 10

        while retries_left > 0:
            try:
                current_status = amqp_request(
                    self.connection,
                    MsgTestSuiteGetStatus(),
                    COMPONENT_ID,
                    use_message_typing=True
                )  # get status
                if isinstance(current_status, MsgTestSuiteGetStatusReply):
                    for tc in current_status.tc_list:
                        if tc['state'] is not None:
                            raise Exception("Session has already (partly) run. Cannot perform full testsuite")

                    logger.debug("Session state seems to be ok to start")
                    return True
                else:
                    raise Exception("Unexpected reply when getting TestSuite status")
            except AmqpSynchCallTimeoutError as e:
                pass  # ignore it

            retries_left -= 1

        raise Exception("Unable to verify testsuite starting state")

    def get_status(self):
        try:
            current_status = amqp_request(
                self.connection,
                MsgTestSuiteGetStatus(),
                COMPONENT_ID,
                use_message_typing=True
            )  # get status

            if isinstance(current_status, MsgTestSuiteGetStatusReply):
                logger.info("Testsuite status: %s", current_status)
            else:
                logger.warning("Could not get testsuite status: unexpected reply")
            pass
        except AmqpSynchCallTimeoutError as e:
            logger.warning("Could not get testsuite status: timeout")


# # # # # # AUXILIARY TEST METHODS # # # # # # #


#######################


if __name__ == '__main__':
    pft = PerformFullTest()
    pft.run()
    pft.stop()
