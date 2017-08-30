from coap_testing_tool import TD_DIR, TD_COAP, TD_COAP_CFG, TD_6LOWPAN
from coap_testing_tool.test_coordinator.coordinator import import_teds
from collections import OrderedDict
import json, unittest, os

"""
python3 -m  pytest coap_testing_tool/extended_test_descriptions/tests/tests.py
"""


class ImportYamlInteropTestCases(unittest.TestCase):
    def test_yaml_testcase_syntax_coap(self):
        imported_tcs = import_teds(TD_COAP)
        for tc in imported_tcs:
            print(tc)
            assert tc.id
            assert tc.uri
            assert tc.objective
            assert tc.configuration_id
            assert tc.references
            assert tc.pre_conditions
            assert tc.notes
            assert tc.sequence

            for step in tc.sequence:
                print(step)
                assert step.id
                assert step.type
                assert step.description

    def test_yaml_testcase_syntax_6lowpan(self):
        imported_tcs = import_teds(TD_6LOWPAN)
        for tc in imported_tcs:
            print(tc)
            assert tc.id
            assert tc.uri
            assert tc.objective
            assert tc.configuration_id
            assert tc.references
            assert tc.pre_conditions
            assert tc.notes
            assert tc.sequence

            for step in tc.sequence:
                print(step)
                assert step.id
                assert step.type
                assert step.description


    def test_yaml_testcase_configuration_syntax_coap(self):
        imported_configs = import_teds(TD_COAP_CFG)
        for tc_config in imported_configs:
            print(tc_config)
            assert tc_config.id
            assert tc_config.uri
            assert tc_config.nodes
            assert tc_config.topology
            assert tc_config.description


if __name__ == '__main__':
    c = ImportYamlInteropTestCases()
    c.test_yaml_testcase_syntax()
