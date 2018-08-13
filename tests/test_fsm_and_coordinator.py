import pprint
import unittest
from time import sleep

from ioppytest import AMQP_URL, AMQP_EXCHANGE
from ioppytest.test_coordinator.coordinator import Coordinator
from ioppytest import TD_COAP_CFG, TD_COAP
from messages import *

COMPONENT_ID = '%s|%s' % ('test_coordinator', 'unitesting')
logger = logging.getLogger(COMPONENT_ID)

default_configuration = {
    "testsuite.testcases": [
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_02",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_03"
    ]
}


class CoordinatorStateMachineTests(unittest.TestCase):
    """
    python3 -m pytest tests/test_fsm_and_coordinator.py

    python3 -m pytest tests/test_fsm_and_coordinator.py::CoordinatorStateMachineTests::test_restart_test_cases
    """

    def setUp(self):
        logger.setLevel(logging.DEBUG)
        self.test_coordinator = Coordinator(amqp_url=AMQP_URL,
                                            amqp_exchange=AMQP_EXCHANGE,
                                            testsuite_name='coap',
                                            ted_config_file=TD_COAP_CFG,
                                            ted_tc_file=TD_COAP)
        self.test_coordinator.bootstrap()

    def test_session_flow_and_emulate_agent_as_a_router_towards_another_network(self):
        """
        python3 -m unittest ioppytest.test_coordinator.tests.tests.CoordinatorStateMachineTests.test_session_flow_and_emulate_agent_as_a_router_towards_another_network

        MsgAgentTunStarted message fields:
                name                     agent_TT
                ipv4_network
                ipv4_netmask
                ipv4_host
                ipv6_no_forwarding       False
                ipv6_host                :3
                ipv6_prefix              bbbb
                re_route_packets_if
                re_route_packets_prefix
                re_route_packets_host
        """

        coap_client_address = ("cccc", "123:456")
        coap_server_address = ("aaaa", "123:456")
        assert self.test_coordinator.state == 'waiting_for_testsuite_config', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.configure_testsuite(MsgSessionConfiguration(configuration=default_configuration))
        assert self.test_coordinator.state != 'waiting_for_testcase_start', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.start_testsuite(MsgTestSuiteStart())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', 'got: %s' % self.test_coordinator.state
        assert self.test_coordinator.testsuite.check_all_iut_nodes_configured() is False

        logger.info('>>> (0) before first Agent Tun Started: %s' % self.test_coordinator.get_nodes_addressing_table())

        self.test_coordinator.handle_iut_configuration_executed(MsgAgentTunStarted(
            name="coap_client",
            re_route_packets_if='some_other_tuntap',
            re_route_packets_prefix=coap_client_address[0],
            re_route_packets_host=coap_client_address[1],
        ))

        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', 'got: %s' % self.test_coordinator.state
        assert self.test_coordinator.testsuite.check_all_iut_nodes_configured() is False

        logger.info('>>> (1) before second Agent Tun Started: %s' % self.test_coordinator.get_nodes_addressing_table())
        self.test_coordinator.handle_iut_configuration_executed(MsgAgentTunStarted(
            name="coap_server",
            re_route_packets_if='some_other_tuntap',
            re_route_packets_prefix=coap_server_address[0],
            re_route_packets_host=coap_server_address[1],
        ))

        logger.info('>>> (2) after second Agent Tun Started: %s' % self.test_coordinator.get_nodes_addressing_table())
        assert self.test_coordinator.state == 'waiting_for_testcase_start', 'got: %s' % self.test_coordinator.state
        assert self.test_coordinator.testsuite.check_all_iut_nodes_configured() is True

        logger.warning(self.test_coordinator.testsuite.get_node_address('coap_client'))
        assert self.test_coordinator.testsuite.get_node_address('coap_client') == coap_client_address
        assert self.test_coordinator.testsuite.get_node_address('coap_server') == coap_server_address

    def test_session_flow_0(self):
        """
        Checks transition
        waiting_for_iut_configuration_executed -> waiting_for_testcase_start
        on events MsgAgentTunStarted
        """

        assert self.test_coordinator.state == 'waiting_for_testsuite_config', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.configure_testsuite(MsgSessionConfiguration(configuration=default_configuration))
        assert self.test_coordinator.state != 'waiting_for_testcase_start', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.start_testsuite(MsgTestSuiteStart())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', 'got: %s' % self.test_coordinator.state
        assert self.test_coordinator.testsuite.check_all_iut_nodes_configured() is False

        logger.info('>>> (0) before first Agent Tun Started: %s' % self.test_coordinator.get_nodes_addressing_table())

        self.test_coordinator.handle_iut_configuration_executed(MsgAgentTunStarted(name="someAgentName1",
                                                                                   ipv6_prefix="bbbb",
                                                                                   ipv6_host="1", ))

        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', 'got: %s' % self.test_coordinator.state
        assert self.test_coordinator.testsuite.check_all_iut_nodes_configured() is False

        logger.info('>>> (1) before second Agent Tun Started: %s' % self.test_coordinator.get_nodes_addressing_table())
        self.test_coordinator.handle_iut_configuration_executed(MsgAgentTunStarted(name="someAgentName2",
                                                                                   ipv6_prefix="bbbb",
                                                                                   ipv6_host="2", ))

        logger.info('>>> (2) after second Agent Tun Started: %s' % self.test_coordinator.get_nodes_addressing_table())
        assert self.test_coordinator.state == 'waiting_for_testcase_start', 'got: %s' % self.test_coordinator.state
        assert self.test_coordinator.testsuite.check_all_iut_nodes_configured() is True

    def test_session_flow_1(self):

        assert self.test_coordinator.state == 'waiting_for_testsuite_config', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.configure_testsuite(MsgSessionConfiguration(configuration=default_configuration))
        assert self.test_coordinator.state != 'waiting_for_testcase_start', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.start_testsuite(MsgTestSuiteStart())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', 'got: %s' % self.test_coordinator.state

        # wait until it times out
        while True:
            sleep(0.2)
            logger.info('wait for tout')
            if self.test_coordinator.state == 'waiting_for_testcase_start':
                logger.info('it timed-out! now we are at waiting_for_testcase_start')
                break

        assert self.test_coordinator.state == 'waiting_for_testcase_start', 'got: %s' % self.test_coordinator.state

        # switch to another testcase
        self.test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_03'))
        logger.info(self.test_coordinator.state)
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_03'))
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed'

        self.__emulate_iut_configuration_messages()

        self.test_coordinator.start_testcase(None)
        assert self.test_coordinator.state == 'waiting_for_step_executed', 'got: %s' % self.test_coordinator.state

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

        logger.info('>>>' + str(self.test_coordinator.state))
        self.test_coordinator.skip_testcase(MsgTestCaseSkip())  # skips current testcase
        sleep(0.3)
        self.test_coordinator.skip_testcase(MsgTestCaseSkip())  # skips current testcase
        logger.info('>>>' + str(self.test_coordinator.state))

    def test_session_flow_2(self):
        """
        skip all testcases
        """

        assert self.test_coordinator.state == 'waiting_for_testsuite_config', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.configure_testsuite(MsgSessionConfiguration(configuration=default_configuration))
        assert self.test_coordinator.state != 'waiting_for_testcase_start', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.start_testsuite(MsgTestSuiteStart())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.skip_testcase(MsgTestCaseSkip())  # skips current testcase
        self.test_coordinator.skip_testcase(MsgTestCaseSkip())  # skips current testcase
        self.test_coordinator.skip_testcase(MsgTestCaseSkip())  # skips current testcase
        logger.info('>>>' + str(self.test_coordinator.state))

    def test_session_flow_3(self):
        """
        select testcases, jumping from one to the other
        """
        assert self.test_coordinator.state == 'waiting_for_testsuite_config', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.configure_testsuite(MsgSessionConfiguration(configuration=default_configuration))
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
        assert self.test_coordinator.state == 'waiting_for_testsuite_config', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.configure_testsuite(
            MsgSessionConfiguration(configuration=default_configuration))  # config 3 TCs
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
        logger.info(self.test_coordinator.state)

    def test_skip_test_case(self):
        """
        Checks transition
        waiting_for_iut_configuration_executed -> waiting_for_testcase_start
        on events MsgAgentTunStarted
        """

        assert self.test_coordinator.state == 'waiting_for_testsuite_config', 'got: %s' % self.test_coordinator.state
        self.test_coordinator.skip_testcase(MsgTestCaseSkip(testcase_id="TD_COAP_CORE_01"))
        self.test_coordinator.start_testsuite(MsgTestSuiteStart())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', 'got: %s' % self.test_coordinator.state
        self.test_coordinator.skip_testcase(MsgTestCaseSkip(testcase_id="TD_COAP_CORE_01"))

    def test_restart_test_case(self):

        assert self.test_coordinator.state == 'waiting_for_testsuite_config', 'got: %s' % self.test_coordinator.state
        self.test_coordinator.configure_testsuite(MsgSessionConfiguration(configuration=default_configuration))

        self.test_coordinator.start_testsuite(MsgTestSuiteStart())

        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', 'got: %s' % self.test_coordinator.state
        self.__emulate_iut_configuration_messages()

        # check we can restart a TC in the middle of the TC execution
        assert self.test_coordinator.testsuite.get_current_step() is None
        self.test_coordinator.start_testcase(MsgTestCaseStart())
        assert self.test_coordinator.state != 'waiting_for_testcase_start', 'got: %s' % self.test_coordinator.state
        print(self.test_coordinator.testsuite.get_current_step_id())
        assert self.test_coordinator.testsuite.get_current_step_id() is not None
        assert self.test_coordinator.testsuite.get_current_step_id() == 'TD_COAP_CORE_01_step_01'
        assert self.test_coordinator.state == 'waiting_for_step_executed', 'got: %s' % self.test_coordinator.state
        self.test_coordinator.step_executed(MsgStepStimuliExecuted(
                node='coap_client'
        ))
        assert self.test_coordinator.testsuite.get_current_step_id() != 'TD_COAP_CORE_01_step_01'
        self.test_coordinator.restart_testcase(MsgTestCaseRestart())
        assert self.test_coordinator.testsuite.get_current_step_id() is None
        assert self.test_coordinator.testsuite.get_current_testcase_id() == 'TD_COAP_CORE_01'

    def test_session_flow_select_last_testcase_assert_that_the_others_will_be_executed_later(self):
        assert self.test_coordinator.state == 'waiting_for_testsuite_config', 'got: %s' % self.test_coordinator.state

        self.test_coordinator.configure_testsuite(MsgSessionConfiguration(configuration=default_configuration))
        assert self.test_coordinator.state != 'waiting_for_testcase_start'

        self.test_coordinator.start_testsuite(MsgTestSuiteStart())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed'

        # check we start in TC1
        assert self.test_coordinator.testsuite.get_current_testcase_id() == 'TD_COAP_CORE_01'

        # jump to TC3, check that we are actually there
        self.test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_03'))
        assert self.test_coordinator.testsuite.get_current_testcase_id() == 'TD_COAP_CORE_03'

        # skip TC3, check we jumped to TC1
        self.test_coordinator.skip_testcase(MsgTestCaseSkip())
        assert self.test_coordinator.testsuite.get_current_testcase_id() == 'TD_COAP_CORE_01'

        # skip TC1, check we jumped to TC2
        self.test_coordinator.skip_testcase(MsgTestCaseSkip())
        assert self.test_coordinator.testsuite.get_current_testcase_id() == 'TD_COAP_CORE_02'

    def test_skip_all_test_cases_check_states_and_report_generation(self):

        assert self.test_coordinator.testsuite.get_report() is None

        # config 3 TCs
        assert self.test_coordinator.state == 'waiting_for_testsuite_config', 'got: %s' % self.test_coordinator.state
        self.test_coordinator.configure_testsuite(MsgSessionConfiguration(configuration=default_configuration))

        # start TS
        assert self.test_coordinator.state == 'waiting_for_testsuite_start', 'got: %s' % self.test_coordinator.state
        self.test_coordinator.start_testsuite(MsgTestSuiteStart())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', 'got: %s' % self.test_coordinator.state

        # skip current
        self.test_coordinator.skip_testcase(MsgTestCaseSkip(testcase_id=None))
        logger.info(pprint.pformat(self.test_coordinator.testsuite.get_testcases_basic()))

        # skip current
        self.test_coordinator.skip_testcase(MsgTestCaseSkip(testcase_id=None))
        logger.info(pprint.pformat(self.test_coordinator.testsuite.get_testcases_basic()))

        # skip current
        self.test_coordinator.skip_testcase(MsgTestCaseSkip(testcase_id=None))
        logger.info(pprint.pformat(self.test_coordinator.testsuite.get_testcases_basic()))

        # test suite finished, test suite report should not be null
        assert self.test_coordinator.state == 'testsuite_finished', 'got: %s' % self.test_coordinator.state
        assert self.test_coordinator.testsuite.get_report() is not None

        logger.info(pprint.pformat(self.test_coordinator.testsuite.get_report()))

    def __emulate_iut_configuration_messages(self):

        self.test_coordinator.iut_configuration_executed(MsgConfigurationExecuted(
            node="coap_server",
            ipv6_address="someAddressFor::coap_client"  # example of pixit
        ))
        assert self.test_coordinator.state != 'waiting_for_testcase_start'

        self.test_coordinator.iut_configuration_executed(MsgConfigurationExecuted(
            node="coap_client",
            ipv6_address="someAddressFor::coap_server"  # example of pixit
        ))
        assert self.test_coordinator.state == 'waiting_for_testcase_start', 'got: %s' % self.test_coordinator.state