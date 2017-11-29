from ioppytest import TD_DIR, TD_COAP, TD_COAP_CFG, TD_6LOWPAN, TD_ONEM2M, TD_ONEM2M_CFG
from ioppytest.test_coordinator.testsuite import import_teds
import unittest

"""
python3 -m  pytest ioppytest/extended_test_descriptions/tests/tests.py
"""


class ImportYamlInteropTestCases(unittest.TestCase):
    def validate_testcase_description(self, tc):
        tc_must_have_fields = {'id', 'uri', 'objective', 'configuration_id', 'references', 'pre_conditions', 'notes',
                               'sequence'}
        tc_must_have_non_null_fields = {'id', 'uri', 'objective', 'configuration_id',
                                        'sequence'}

        for field in tc_must_have_fields:
            assert hasattr(tc, field), 'TC yaml file must contain a %s field' % field

        for field in tc_must_have_non_null_fields:
            assert getattr(tc, field) is not None, 'TC yaml file must contain NOT NULL %s field' % field

    def validate_step_description(self, step):

        step_must_have_fields = {'id', 'type', 'description'}
        step_must_have_non_null_fields = {'id', 'type', 'description'}

        for field in step_must_have_fields:
            assert hasattr(step, field), 'STEP in yaml file must contain a %s field' % field

        for field in step_must_have_non_null_fields:
            assert hasattr(step, field), 'STEP in yaml file must contain NOT NULL %s field' % field

    def validate_config_description(self, config):

        tc_config_must_have_fields = {'id', 'uri', 'nodes', 'topology',
                                      'description'}
        tc_config_must_have_non_null_fields = {'id', 'uri', 'nodes', 'topology',
                                               'description'}

        for field in tc_config_must_have_fields:
            assert hasattr(config, field), 'CONFIG yaml file must contain a %s field' % field

        for field in tc_config_must_have_non_null_fields:
            assert getattr(config, field) is not None, 'TC yaml file must contain NOT NULL %s field' % field

    def test_yaml_testcase_syntax_coap(self):
        imported_tcs = import_teds(TD_COAP)
        for tc in imported_tcs:
            self.validate_testcase_description(tc)

            for step in tc.sequence:
                self.validate_step_description(step)

    def test_yaml_testcase_syntax_6lowpan(self):
        imported_tcs = import_teds(TD_6LOWPAN)

        for tc in imported_tcs:
            self.validate_testcase_description(tc)

            for step in tc.sequence:
                self.validate_step_description(step)

    def test_yaml_testcase_configuration_syntax_coap(self):
        imported_configs = import_teds(TD_COAP_CFG)
        for tc_config in imported_configs:
            self.validate_config_description(tc_config)

    def test_yaml_testcase_syntax_oneM2M(self):
        imported_tcs = import_teds(TD_ONEM2M)

        for tc in imported_tcs:
            self.validate_testcase_description(tc)

            for step in tc.sequence:
                self.validate_step_description(step)

if __name__ == '__main__':
    c = ImportYamlInteropTestCases()
    c.test_yaml_testcase_syntax()
