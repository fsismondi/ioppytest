import logging
import pprint
import unittest

from ioppytest import TEST_DESCRIPTIONS_DICT, TEST_DESCRIPTIONS_CONFIGS_DICT
from ioppytest.test_descriptions.testsuite import TestSuite

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


class TestSuiteTests(unittest.TestCase):
    """
    python3 -m unittest ioppytest.test_coordinator.tests.test_fsm_and_coordinator.TestSuiteTests -vvv
    """

    def setUp(self):

        proto = 'coap'
        pprint.pprint(TEST_DESCRIPTIONS_DICT[proto])

        self.testsuite = TestSuite(
            ted_tc_file=TEST_DESCRIPTIONS_DICT[proto],
            ted_config_file=TEST_DESCRIPTIONS_CONFIGS_DICT[proto],
        )

        print("Got %s testcases for test suite" % len(self.testsuite.get_testcases_list()))

    def _run_all_getters(self):
        logger.info(self.testsuite.get_detailed_status())

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

    def test_testcases_list_at_least_length_of_one(self):
        assert len(self.testsuite.get_testcases_list()) >= 1, "%s got zero test cases" % self.testsuite

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


class TestSuiteTestsForCoAPTestDescription(TestSuiteTests):
    def setUp(self):
        proto = 'coap'
        pprint.pprint(TEST_DESCRIPTIONS_DICT[proto])

        self.testsuite = TestSuite(
            ted_tc_file=TEST_DESCRIPTIONS_DICT[proto],
            ted_config_file=TEST_DESCRIPTIONS_CONFIGS_DICT[proto],
        )

        print("Got %s testcases for test suite" % len(self.testsuite.get_testcases_list()))


class TestSuiteTestsFor6LoWPANTestDescription(TestSuiteTests):
    def setUp(self):
        proto = '6lowpan'
        pprint.pprint(TEST_DESCRIPTIONS_DICT[proto])

        self.testsuite = TestSuite(
            ted_tc_file=TEST_DESCRIPTIONS_DICT[proto],
            ted_config_file=TEST_DESCRIPTIONS_CONFIGS_DICT[proto],
        )

        print("Got %s testcases for test suite" % len(self.testsuite.get_testcases_list()))


class TestSuiteTestsForCoMITestDescription(TestSuiteTests):
    def setUp(self):
        proto = 'comi'
        pprint.pprint(TEST_DESCRIPTIONS_DICT[proto])

        self.testsuite = TestSuite(
            ted_tc_file=TEST_DESCRIPTIONS_DICT[proto],
            ted_config_file=TEST_DESCRIPTIONS_CONFIGS_DICT[proto],
        )

        print("Got %s testcases for test suite" % len(self.testsuite.get_testcases_list()))


class TestSuiteTestsForOneM2MTestDescription(TestSuiteTests):
    def setUp(self):
        proto = 'onem2m'
        pprint.pprint(TEST_DESCRIPTIONS_DICT[proto])

        self.testsuite = TestSuite(
            ted_tc_file=TEST_DESCRIPTIONS_DICT[proto],
            ted_config_file=TEST_DESCRIPTIONS_CONFIGS_DICT[proto],
        )

        print("Got %s testcases for test suite" % len(self.testsuite.get_testcases_list()))


class TestSuiteTestsForLwM2MTestDescription(TestSuiteTests):
    def setUp(self):
        proto = 'lwm2m'
        pprint.pprint(TEST_DESCRIPTIONS_DICT[proto])

        self.testsuite = TestSuite(
            ted_tc_file=TEST_DESCRIPTIONS_DICT[proto],
            ted_config_file=TEST_DESCRIPTIONS_CONFIGS_DICT[proto],
        )

        print("Got %s testcases for test suite" % len(self.testsuite.get_testcases_list()))
