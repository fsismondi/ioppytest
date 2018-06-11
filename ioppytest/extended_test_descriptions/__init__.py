import yaml
import logging
from ioppytest.test_coordinator.testsuite import TestCase, TestSuite, TestConfig, TestSuiteError

from ioppytest import (
    TEST_DESCRIPTIONS_CONFIGS_DICT,
    TEST_DESCRIPTIONS_DICT,
)

_test_descriptions_and_configurations_paths = []
_test_descriptions_and_configurations_paths += list(TEST_DESCRIPTIONS_DICT.values())
_test_descriptions_and_configurations_paths += list(TEST_DESCRIPTIONS_CONFIGS_DICT.values())

_flat_list_of_test_descriptions_and_configurations = [
    item for sublist in _test_descriptions_and_configurations_paths for item in sublist
]

__td_testcases_list = []
__td_testcases_dict = {}
__td_config_list = []
__td_config_dict = {}

for TD in _flat_list_of_test_descriptions_and_configurations:
    with open(TD, "r", encoding="utf-8") as stream:
        yaml_docs = yaml.load_all(stream)
        for yaml_doc in yaml_docs:
            if type(yaml_doc) is TestCase:
                __td_testcases_list.append(yaml_doc)
                __td_testcases_dict[yaml_doc.id] = yaml_doc
            elif type(yaml_doc) is TestConfig:
                __td_config_list.append(yaml_doc)
                __td_config_dict[yaml_doc.id] = yaml_doc
            else:
                logging.warning("Unrecognised yaml structure: %s" % str(yaml_doc))


def get_list_of_all_test_cases():
    return __td_testcases_list


def get_dict_of_all_test_cases():
    return __td_testcases_dict


def get_list_of_all_test_cases_configurations():
    return __td_config_list


def get_dict_of_all_test_cases_configurations():
    return __td_config_dict


def get_test_cases_list_from_yaml(testdescription_yamlfile):
    """
    :param testdescription_yamlfile:
    :return: TC objects
    """

    list = []
    with open(testdescription_yamlfile, "r", encoding="utf-8") as stream:
        yaml_docs = yaml.load_all(stream)
        for yaml_doc in yaml_docs:
            if type(yaml_doc) is TestCase:
                list.append(yaml_doc)
    return list


def get_test_configurations_list_from_yaml(testdescription_yamlfile):
    """
    :param testdescription_yamlfile:
    :return: TC config objects
    """

    list = []
    with open(testdescription_yamlfile, "r", encoding="utf-8") as stream:
        yaml_docs = yaml.load_all(stream)
        for yaml_doc in yaml_docs:
            if type(yaml_doc) is TestConfig:
                list.append(yaml_doc)
    return list
