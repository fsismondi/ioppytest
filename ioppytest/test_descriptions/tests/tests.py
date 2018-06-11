import pprint
import unittest

from ioppytest import TEST_DESCRIPTIONS, TEST_DESCRIPTIONS_CONFIGS
from ioppytest.test_descriptions import format_conversion
from ioppytest.test_descriptions.testsuite import import_teds

"""
python3 -m  pytest ioppytest/test_descriptions/tests/tests.py

or verbose unitest:

python3 -m unittest ioppytest/test_descriptions/tests/tests.py
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
                                      'nodes_description', 'configuration_diagram'}
        tc_config_must_have_non_null_fields = {'id', 'uri', 'nodes', 'topology',
                                               'nodes_description'}

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

    def test_check_that_every_testcase_uses_an_existent_config_id(self):
        tc_configs = []
        for tc_config_filename in TEST_DESCRIPTIONS_CONFIGS:
            imported_configs = import_teds(tc_config_filename)
            assert type(imported_configs) is list

            # get all test config ids
            for i in imported_configs:
                tc_configs.append(i.id)

        for td in TEST_DESCRIPTIONS:
            imported_tcs = import_teds(td)
            for tc in imported_tcs:
                assert tc.configuration_id in tc_configs, 'couldnt find <{}> among config files'.format(
                    tc.configuration_id)

    def test_all_testcases_id_are_uppercase(self):
        for td in TEST_DESCRIPTIONS:
            imported_tcs = import_teds(td)
            for tc in imported_tcs:
                assert tc.configuration_id == tc.configuration_id.upper(), \
                    'TC %s contains lower cases in testcase id' % tc.id

    def test_all_testcases_config_ids_are_uppercase(self):
        for tc_config_filename in TEST_DESCRIPTIONS_CONFIGS:
            imported_tcs = import_teds(tc_config_filename)
            for tc_conf in imported_tcs:
                assert tc_conf.id == tc_conf.id.upper(), \
                    'TC %s contains lower cases in test config id' % tc_conf.id


class TestDescriptionFormatReprAndConvertion(unittest.TestCase):
    def setUp(self):

        self.imported_tcs = []
        self.imported_tc_configs = []

        for td in TEST_DESCRIPTIONS:
            self.imported_tcs += import_teds(td)

        print("got %s test cases: %s" % (
            len(self.imported_tcs),
            pprint.pformat([item.id for item in self.imported_tcs])
        ))

        for td in TEST_DESCRIPTIONS_CONFIGS:
            print('parsing %s ' % td)
            self.imported_tc_configs += import_teds(td)

        print("got %s test cases configs: %s" % (
            len(self.imported_tc_configs),
            pprint.pformat([item.id for item in self.imported_tc_configs])
        ))

        assert len(self.imported_tc_configs) > 0

    def test_get_markdown_representation_of_testcase(self):
        for i in self.imported_tcs:
            print(format_conversion.get_markdown_representation_of_testcase(i.id))

    def test_get_markdown_representation_of_testcase_config(self):
        for i in self.imported_tc_configs:
            print('markdown repr for %s' % i.id)
            print(format_conversion.get_markdown_representation_of_testcase_configuration(i.id))
            print(format_conversion.get_markdown_representation_of_testcase_configuration(i.id, include_diagram=True))

    def test_ascii_art_diagrams_in_test_config_yaml_documents(self):
        for tc_conf in self.imported_tc_configs:
            if hasattr(tc_conf, 'configuration_diagram') and tc_conf.configuration_diagram:
                print(tc_conf.configuration_diagram)
