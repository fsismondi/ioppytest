from ioppytest import TEST_DESCRIPTIONS, TEST_DESCRIPTIONS_CONFIGS
from ioppytest.test_coordinator.testsuite import import_teds
import unittest

"""
python3 -m  pytest ioppytest/extended_test_descriptions/tests/tests.py

or verbose unitest:

python3 -m unittest ioppytest/extended_test_descriptions/tests/tests.py
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

    def test_validate_test_descriptions(self):
        for td in TEST_DESCRIPTIONS:
            imported_tcs = import_teds(td)
            for tc in imported_tcs:
                print('validating %s (...)' % str(tc)[:70])
                self.validate_testcase_description(tc)

                for step in tc.sequence:
                    self.validate_step_description(step)

    def test_validate_test_description_configurations(self):
        for td in TEST_DESCRIPTIONS_CONFIGS:
            imported_configs = import_teds(td)
            for tc_config in imported_configs:
                print('validating %s (...)' % str(tc_config)[:70])
                self.validate_config_description(tc_config)
