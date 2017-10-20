import unittest, logging, os, pika, json
from time import sleep
from coap_testing_tool.utils.event_bus_messages import *
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE, TD_COAP_CFG, TD_COAP
from coap_testing_tool.test_coordinator.testsuite import import_teds
from coap_testing_tool.test_coordinator.states_machine import Coordinator

COMPONENT_ID = '%s|%s' % ('test_coordinator', 'unitesting')
# init logging to stnd output and log files
logger = logging.getLogger(COMPONENT_ID)


class CoordinatorStateMachineTests(unittest.TestCase):
    """
    python3 -m unittest coap_testing_tool.test_coordinator.tests.tests.CoordinatorStateMachineTests
    """
    def setUp(self):
        logger.setLevel(logging.DEBUG)
        from coap_testing_tool import TD_COAP_CFG, TD_COAP
        self.test_coordinator = Coordinator(amqp_url=AMQP_URL,
                                            amqp_exchange=AMQP_EXCHANGE,
                                            ted_config_file=TD_COAP_CFG,
                                            ted_tc_file=TD_COAP)
        self.test_coordinator.bootstrap()

    def test_session_flow_1(self):

        assert self.test_coordinator.state == 'waiting_for_testsuite_config'

        self.test_coordinator.configure_testsuite(MsgInteropSessionConfiguration())
        assert self.test_coordinator.state != 'waiting_for_testcase_start'

        self.test_coordinator.start_testsuite(MsgTestSuiteStart())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed'

        # wait until it times out
        while True:
            sleep(0.2)
            print('wait for tout')
            if self.test_coordinator.state == 'waiting_for_testcase_start':
                print('it timed-out! now we are at waiting_for_testcase_start')
                break

        assert self.test_coordinator.state == 'waiting_for_testcase_start'

        # switch to another testcase
        self.test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_03'))
        print(self.test_coordinator.state)
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed'

        self.test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_03'))
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed'

        self.test_coordinator.iut_configuration_executed(MsgConfigurationExecuted(
            node="coap_server",
            ipv6_address="someAddress"  # example of pixit
        ))
        assert self.test_coordinator.state != 'waiting_for_testcase_start'

        self.test_coordinator.iut_configuration_executed(MsgConfigurationExecuted(
            node="coap_client",
            ipv6_address="someAddress"  # example of pixit
        ))
        print(self.test_coordinator.state)
        assert self.test_coordinator.state == 'waiting_for_testcase_start'

        self.test_coordinator.start_testcase(None)
        assert self.test_coordinator.state == 'waiting_for_step_executed'

        self.test_coordinator.step_executed(MsgStepStimuliExecuted(
            node='coap_client'
        ))

        self.test_coordinator.step_executed(MsgStepVerifyExecuted(
            node='coap_server',
            verify_response=True
        ))
        self.test_coordinator.step_executed(MsgStepVerifyExecuted(
            node='coap_client',
            verify_response=True
        ))

        print('>>>' + str(self.test_coordinator.state))
        self.test_coordinator.skip_testcase(MsgTestCaseSkip())  # skips current testcase
        sleep(0.3)
        self.test_coordinator.skip_testcase(MsgTestCaseSkip())  # skips current testcase
        print('>>>' + str(self.test_coordinator.state))

    def test_session_flow_2(self):
        """
        skip all testcases
        """

        assert self.test_coordinator.state == 'waiting_for_testsuite_config'

        self.test_coordinator.configure_testsuite(MsgInteropSessionConfiguration())
        assert self.test_coordinator.state != 'waiting_for_testcase_start'

        self.test_coordinator.start_testsuite(MsgTestSuiteStart())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed'

        self.test_coordinator.skip_testcase(MsgTestCaseSkip())  # skips current testcase
        self.test_coordinator.skip_testcase(MsgTestCaseSkip())  # skips current testcase
        self.test_coordinator.skip_testcase(MsgTestCaseSkip())  # skips current testcase
        print('>>>' + str(self.test_coordinator.state))

    def test_session_flow_3(self):
        """
        select testcases, then skip all
        """
        assert self.test_coordinator.state == 'waiting_for_testsuite_config'

        self.test_coordinator.configure_testsuite(MsgInteropSessionConfiguration())
        assert self.test_coordinator.state != 'waiting_for_testcase_start'

        self.test_coordinator.start_testsuite(MsgTestSuiteStart())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed'

        self.test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_03'))
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed'

        self.test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_02'))
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed'

        self.test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_01'))
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed'

    def test_session_flow_4(self):
        """
        abort all testcase
        """
        assert self.test_coordinator.state == 'waiting_for_testsuite_config'

        self.test_coordinator.configure_testsuite(MsgInteropSessionConfiguration())  # config 3 TCs
        assert self.test_coordinator.state != 'waiting_for_testcase_start'

        self.test_coordinator.start_testsuite(MsgTestSuiteStart())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', \
            "expected waiting for iut confnig, but found %s" % self.test_coordinator.state

        self.test_coordinator.abort_testcase(MsgTestCaseAbort())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', \
            "expected waiting for iut confnig, but found %s" % self.test_coordinator.state
        self.test_coordinator.abort_testcase(MsgTestCaseAbort())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', \
            "expected waiting for iut confnig, but found %s" % self.test_coordinator.state
        self.test_coordinator.abort_testcase(MsgTestCaseAbort())
        assert self.test_coordinator.state == 'testsuite_finished', \
            "expected waiting for iut confnig, but found %s" % self.test_coordinator.state
        print(self.test_coordinator.state)
