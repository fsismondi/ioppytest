import unittest, logging, os, pika, json
from time import sleep
from ioppytest.utils.messages import *
from ioppytest import AMQP_URL, AMQP_EXCHANGE, TD_COAP_CFG, TD_COAP
from ioppytest.test_coordinator.testsuite import import_teds, TestSuite
from ioppytest.test_coordinator.states_machine import Coordinator
from ioppytest.utils.event_bus_utils import AmqpSynchCallTimeoutError

COMPONENT_ID = '%s|%s' % ('test_coordinator', 'unitesting')
# init logging to stnd output and log files
logger = logging.getLogger(COMPONENT_ID)

default_configuration = {
    "testsuite.testcases": [
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_02",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_03"
    ]
}


class TestSuiteTests(unittest.TestCase):
    """
    python3 -m unittest ioppytest.test_coordinator.tests.tests.TestSuiteTests
    """

    def setUp(self):
        logger.setLevel(logging.DEBUG)
        from ioppytest import TD_COAP_CFG, TD_COAP
        self.testsuite = TestSuite(
            ted_tc_file=TD_COAP,
            ted_config_file=TD_COAP_CFG)

    def _run_all_getters(self):
        # logger.info(self.testsuite.get_detailed_status())

        self.testsuite.get_addressing_table()
        self.testsuite.get_testsuite_configuration()
        self.testsuite.get_testcases_basic()

        try:
            self.testsuite.get_testcase('foo')
        except ValueError:
            pass  # passed

        self.testsuite.get_addressing_table()

        self.testsuite.get_agent_names()

        self.testsuite.get_current_step()
        self.testsuite.get_current_step_id()
        self.testsuite.get_current_step_state()
        self.testsuite.get_current_step_target_address()

        self.testsuite.get_testcases_list()

        self.testsuite.get_current_testcase()
        self.testsuite.get_current_testcase_id()
        self.testsuite.get_current_testcase_state()
        self.testsuite.get_current_testcase_configuration()
        self.testsuite.get_current_testcase_configuration_id()

        self.testsuite.get_report()
        self.testsuite.get_testcases_basic()
        self.testsuite.get_testcase_report()

        self.testsuite.get_detailed_status()
        self.testsuite.get_default_iut_addressing_from_configurations()

    def test_all_getters_of_testsuite_on_init(self):
        self._run_all_getters()

    def test_all_getters_of_testsuite_on_middle_way(self):
        log_trace = []

        self._run_all_getters()

        logger.info(self.testsuite.states_summary())
        tc = self.testsuite.next_testcase()

        for t in range(0, 83):
            tc = self.testsuite.get_current_testcase()
            if self.testsuite.check_testcase_finished():
                tc = self.testsuite.next_testcase()
                self._run_all_getters()

            ts = self.testsuite.next_step()
            self._run_all_getters()

            if ts:
                if ts.type != 'stimuli':
                    ts.set_result('pass', 'faked passed verdict')
                ts.change_state('finished')

            if tc and ts:
                log_trace.append((tc.id, ts.id))
            elif tc:
                log_trace.append((tc.id, '-'))
            else:
                log_trace.append(('-', '-'))

            self._run_all_getters()

        for item in log_trace:
            logger.info(item)

        self._run_all_getters()

        logger.info("report: %s" % self.testsuite.generate_report())

    def test_all_getters_of_testsuite_on_finished(self):
        log_trace = []

        self._run_all_getters()

        tc = self.testsuite.next_testcase()

        while tc:

            if self.testsuite.check_testcase_finished():
                logger.info('finished %s' % self.testsuite.get_current_testcase().id)
                self.testsuite.get_current_testcase().change_state('finished')
                tc = self.testsuite.next_testcase()
                self._run_all_getters()

            ts = self.testsuite.next_step()
            self._run_all_getters()

            if ts:
                if ts.type != 'stimuli':
                    ts.set_result('pass', 'faked passed verdict')
                ts.change_state('finished')

            if tc and ts:
                log_trace.append((tc.id, ts.id))
            elif tc:
                log_trace.append((tc.id, '-'))
            else:
                log_trace.append(('-', '-'))

            self._run_all_getters()

        for item in log_trace:
            logger.info(item)

        self._run_all_getters()

        logger.info("report: %s" % self.testsuite.generate_report())

    def test_check_testcase_finished(self):
        assert self.testsuite.current_tc is None
        self.testsuite.get_testsuite_configuration()
        self.testsuite.get_testsuite_configuration()

    def test_address_table_updates(self):

        add_table_1 = self.testsuite.get_addressing_table().copy()
        logger.info(add_table_1)
        assert add_table_1 is not None

        self.testsuite.update_node_address(node='foo', address=('var1', 'var2'))
        add_table_2 = self.testsuite.get_addressing_table().copy()
        logger.info(add_table_2)
        assert len(add_table_1) == len(add_table_2) - 1

        assert self.testsuite.check_all_iut_nodes_configured() is False

        self.testsuite.update_node_address(node='foo2', address=('var1', 'var2'))
        add_table_3 = self.testsuite.get_addressing_table().copy()
        logger.info(add_table_3)
        assert len(add_table_2) == len(add_table_3) - 1

        assert self.testsuite.check_all_iut_nodes_configured() is True


class CoordinatorStateMachineTests(unittest.TestCase):
    """
    python3 -m unittest ioppytest.test_coordinator.tests.tests.CoordinatorStateMachineTests
    """

    def setUp(self):
        logger.setLevel(logging.DEBUG)
        from ioppytest import TD_COAP_CFG, TD_COAP
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
        coap_server_address = ("aaaa","123:456")
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

        self.test_coordinator.iut_configuration_executed(MsgConfigurationExecuted(
            node="coap_server",
            ipv6_address="someAddressFor::coap_server"  # example of pixit
        ))
        assert self.test_coordinator.state != 'waiting_for_testcase_start'

        self.test_coordinator.iut_configuration_executed(MsgConfigurationExecuted(
            node="coap_client",
            ipv6_address="someAddressFor::coap_server"  # example of pixit
        ))
        logger.info(self.test_coordinator.state)
        assert self.test_coordinator.state == 'waiting_for_testcase_start', 'got: %s' % self.test_coordinator.state

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
        select testcases, then skip all
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

    def test_skip_test_cases(self):
        """
        Checks transition
        waiting_for_iut_configuration_executed -> waiting_for_testcase_start
        on events MsgAgentTunStarted
        """

        assert self.test_coordinator.state == 'waiting_for_testsuite_config', 'got: %s' % self.test_coordinator.state
        self.test_coordinator.skip_testcase(MsgTestCaseSkip(testcase_id = "TD_COAP_CORE_01"))
        self.test_coordinator.start_testsuite(MsgTestSuiteStart())
        assert self.test_coordinator.state == 'waiting_for_iut_configuration_executed', 'got: %s' % self.test_coordinator.state
        self.test_coordinator.skip_testcase(MsgTestCaseSkip(testcase_id="TD_COAP_CORE_01"))

        logger.info(self.test_coordinator.testsuite.get_testcases_basic())
        logger.info(self.test_coordinator.testsuite.get_testcase_report())
        logger.info(self.test_coordinator.testsuite.get_report())

