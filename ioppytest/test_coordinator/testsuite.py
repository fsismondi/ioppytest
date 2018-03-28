# -*- coding: utf-8 -*-
# !/usr/bin/env python3
import os
import json
import yaml
import logging
import fileinput

from itertools import cycle
from collections import OrderedDict

from ioppytest import AMQP_URL, AMQP_EXCHANGE, LOG_LEVEL, TD_DIR
from ioppytest.utils.exceptions import TestSuiteError
from ioppytest.utils.rmq_handler import RabbitMQHandler, JsonFormatter

COMPONENT_ID = '%s|%s' % ('test_coordinator', 'testsuite')

# init logging to stnd output and log files
logger = logging.getLogger(COMPONENT_ID)
logger.setLevel(LOG_LEVEL)

ANALYSIS_MODE = 'post_mortem'  # either step_by_step or post_mortem

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)


# # # YAML parser methods # # #
def testcase_constructor(loader, node):
    instance = TestCase.__new__(TestCase)
    yield instance
    state = loader.construct_mapping(node, deep=True)
    logger.debug("pasing test case: " + str(state))
    instance.__init__(**state)


def test_config_constructor(loader, node):
    instance = TestConfig.__new__(TestConfig)
    yield instance
    state = loader.construct_mapping(node, deep=True)
    # logger.debug("passing test case: " + str(state))
    instance.__init__(**state)


# these build Testcase and Configuration objects from yaml files
yaml.add_constructor(u'!configuration', test_config_constructor)
yaml.add_constructor(u'!testcase', testcase_constructor)


def merge_yaml_files(filelist: list):
    new_merged_file = os.path.join(TD_DIR, 'merged_files.yaml')

    with open(new_merged_file, 'w', encoding="utf-8") as fout:
        for file in filelist:
            with open(file, 'r', encoding="utf-8") as fin:
                for line in fin:
                    if line.startswith("#"):
                        pass
                    else:
                        fout.write(line)
            fout.write(os.linesep)

    return new_merged_file


def import_teds(yamlfile):
    """
    :param yamlfile: TED yaml file
    :return: list of imported testCase(s) and testConfig(s) object(s)
    """
    td_list = []
    with open(yamlfile, "r", encoding="utf-8") as stream:
        yaml_docs = yaml.load_all(stream)
        for yaml_doc in yaml_docs:
            # TODO use same yaml for both test cases and config descriptions
            if type(yaml_doc) is TestCase:
                logger.debug(' Parsed test case: %s from yaml file: %s :' % (yaml_doc.id, yamlfile))
                td_list.append(yaml_doc)
            elif type(yaml_doc) is TestConfig:
                logger.debug(' Parsed test case config: %s from yaml file: %s :' % (yaml_doc.id, yamlfile))
                td_list.append(yaml_doc)
            else:
                logger.error('Couldnt processes import: %s from %s' % (str(yaml_doc), yamlfile))
    return td_list


# def yaml_include(loader, node):
#     # Get the path out of the yaml file
#     file_name = os.path.join(os.path.dirname(loader.name), node.value)
#
#     with open(file_name) as inputfile:
#         return yaml.load(inputfile)
#
# yaml.add_constructor("!include", yaml_include)
# yaml.add_constructor(u'!configuration', testcase_constructor)


# # # Auxiliary functions # # #

def list_to_str(ls):
    """
    flattens a nested list up to two levels of depth

    :param ls: the list
    :return: single string with all the items inside the list
    """

    ret = ''
    for l in ls:
        if isinstance(l, list):
            for sub_l in l:
                if isinstance(sub_l, list):
                    # I truncate in the second level
                    pass
                else:
                    ret += sub_l + '\n'
        else:
            ret += l + '\n'
    return ret


# # # Test suite models # # #

class TestSuite:
    def __init__(self, ted_tc_file, ted_config_file):

        # first let's import the TC configurations
        if type(ted_config_file) is list:
            ted_config_file = merge_yaml_files(ted_config_file)
        imported_configs = import_teds(ted_config_file)
        self.tc_configs = OrderedDict()
        self.agents = set()

        for tc_config in imported_configs:
            self.tc_configs[tc_config.id] = tc_config
            self.agents |= set(tc_config.nodes)

        logger.info('Imports: %s TC_CONFIG imported' % len(self.tc_configs))
        logger.info('Imports: found the following agents from TC_CONFIG %s' % list(self.agents))

        for key, val in self.tc_configs.items():
            logger.info('test configuration imported from YAML: %s' % key)

        # lets import TCs and make sure there's a tc config for each one of them
        if type(ted_tc_file) is list:
            ted_tc_file = merge_yaml_files(ted_tc_file)
        imported_teds = import_teds(ted_tc_file)
        self.teds = OrderedDict()
        for ted in imported_teds:
            self.teds[ted.id] = ted
            assert ted.configuration_id in self.tc_configs, \
                "Missing config: %s for test case: %s " % (ted.configuration_id, ted.id)

        logger.info('Imports: %s TC execution scripts imported' % len(self.teds))
        for key, val in self.teds.items():
            logger.info('test case imported from YAML: %s' % key)

        # test cases iterator (over the TC objects, not the keys)
        self._ted_it = cycle(self.teds.values())
        self.current_tc = None

        # session info (published in bus after testing tool is spawned):
        self.session_id = None
        self.session_users = None
        self.session_configuration = None
        self.session_selected_tc_list = None

        # final testsuite report
        self.report = None

    def states_summary(self):
        summary = OrderedDict()
        summary.update(
            {
                'started': False,
            }
        )
        if self.current_tc:
            summary.update(
                {
                    'started': True,
                    'testcase_id': self.current_tc.id,
                    'testcase_state': self.current_tc.state,
                }
            )
            if self.current_tc.current_step:
                summary.update(self.current_tc.current_step.to_dict(verbose=True))
        else:
            summary.update({'testcase_id': None,
                            'testcase_state': None, })
        return summary

    def next_testcase(self):
        """
        Circularly iterates over the testcases, the returned on (returned as current_tc) must be
        a non executed, or skipped one
        :return: current test case (Tescase object) or None if nothing else left to execute
        """

        # _ted_it is a circular iterator (testcase can eventually be executed out of order due tu user selection)
        self.current_tc = next(self._ted_it)

        # get next not executed nor skipped testcase:
        max_iters = len(self.teds)
        while self.current_tc.state is not None:
            self.current_tc = self._ted_it.__next__()
            max_iters -= 1
            if max_iters < 0:
                self.current_tc = None
                return None

        return self.current_tc

    def go_to_testcase(self, testcase_id):
        """
        Jumps to testcase_id
        :return: current test case (Tescase object) or None if testcase_id not found
        """
        if testcase_id:
            assert type(testcase_id) is str

        tc_selected = self.get_testcase(testcase_id)

        if tc_selected:
            self.current_tc = tc_selected
        else:
            raise TestSuiteError('Testcase not found')

        self.current_tc.reinit()

    def next_step(self):
        """
        Simple iterator over the steps.
        Goes to next TC if current_TC is None or finished
        :return: step or None if testcase finished

        """
        assert self.current_tc

        try:
            # if None then nothing else to execute
            if self.current_tc is None:
                return None

            self.current_tc.current_step = next(self.current_tc._step_it)

            # skip postponed steps
            while self.current_tc.current_step.state == 'postponed':
                self.current_tc.current_step = next(self.current_tc._step_it)

        except StopIteration:
            logger.info('Test case finished. No more steps to execute in testcase: %s' % self.current_tc.id)
            # return None when TC finished
            return None

        # update step state to executing
        self.current_tc.current_step.change_state('executing')

        logger.debug('Next step to execute: %s' % self.current_tc.current_step.id)

        return self.current_tc.current_step

    def generate_report(self):
        """
        :return: list of reports
        """
        report = []
        for tc in self.teds.values():
            report_item = {'testcase_id': tc.id}

            if tc.report is None:
                logger.warning("Empty report found. Generating dummy report for skipped testcase : %s" % tc.id)
                tc.generate_testcases_verdict(None)
            else:
                report_item.update(tc.report)
            report.append(report_item)
        self.report = report

    def get_report(self):
        return self.report

    def reinit(self, tc_list_selection=None):
        # resets all previously executed TC
        for tc in self.teds.values():
            tc.reinit()

        # reconfigure test cases selection
        if tc_list_selection:
            self.configure_testsuite(tc_list_selection)
        elif self.session_selected_tc_list:
            self.configure_testsuite(self.session_selected_tc_list)

    def abort_current_testcase(self):
        self.current_tc.abort()
        self.current_tc = None

    def set_iut_configuration(self, node, node_address):
        if node and node_address:
            self.get_current_testcase_configuration().update_node_address(node, node_address)
            config = self.get_current_testcase_configuration().to_dict(verbose=True)
            logger.info(
                'IUT/EUT addresses updated: %s, topology: %s' % (config['addressing_table'], config['topology']))
        else:
            raise TestSuiteError('Expected node_id and node_address (%s), but got %s , %s ' %
                                 (
                                     str(type(node_address)),
                                     node,
                                     node_address
                                 ))

    def get_current_step_target_address(self):
        # should return using format bbbb::1 , bbbb::2 , etc..
        node = self.current_tc.current_step.iut.node
        config = self.get_current_testcase_configuration()
        address_tuple = config.get_target_address(node)

        assert len(address_tuple) == 2

        return "%s::%s" % address_tuple

    def check_all_iut_nodes_configured(self):
        current_config = self.get_current_testcase_configuration()
        return current_config.check_all_iut_nodes_configured()

    def check_testcase_finished(self):
        return self.current_tc.check_all_steps_finished()

    def check_testsuite_finished(self):
        # cyclic as user may not have started by the first TC
        it = cycle(self.teds.values())

        # we need to check if we already did a cycle (cycle doesnt raises StopIteration)
        iter_counts = len(self.teds)
        tc = next(it)

        while iter_counts >= 0:
            # check that there's no steps in state = None or executing
            if tc.state in (None, 'executing', 'ready_for_analysis', 'analyzing'):
                logger.debug("Got unfinished test case: %s, on state: %s" % (tc.id, tc.state))
                return False
            else:  # TC state is 'skipped' or 'finished'
                tc = next(it)
            iter_counts -= 1
        if iter_counts < 0:
            logger.debug("Testsuite finished. No more test cases to execute.")
            return True

    def configure_testsuite(self, tc_list_requested, session_id=None, users=None, configuration=None):
        assert tc_list_requested is not None

        # this info is not used in the testing tool
        self.session_id = session_id
        self.session_users = users
        self.session_configuration = configuration
        # make all testcases id uppercase
        self.session_selected_tc_list = [x.upper() for x in tc_list_requested]

        # get all TCs
        tc_list_available = self.get_testcases_list()

        # verify if selected TCs are available
        tc_non_existent = list(set(tc_list_requested) - set(tc_list_available))
        tc_to_skip = list(set(tc_list_available) - set(tc_list_requested))

        if len(tc_list_requested) == 0:
            logger.error('No testcases selected. Using default selection: ALL')
            return

        if len(tc_non_existent) != 0:
            logger.error('The following testcases are not available in the testing tool: %s' % str(tc_non_existent))

        # let's set as skipped all non requested testcases
        if len(tc_to_skip) != 0:
            for item in sorted(tc_to_skip):
                self.skip_testcase(item)

    def get_agent_names(self):
        return list(self.agents)

    def get_testsuite_configuration(self):

        resp = {}
        resp.update({'session_id': self.session_id})
        resp.update({'users': self.session_users})
        resp.update({'configuration': self.session_configuration})
        resp.update({'tc_list': self.get_testcases_basic(verbose=True)})
        return resp

    def skip_testcase(self, testcase_id=None):
        """
        This can skip ongoing testcases or set non-ongoing testcase into skipped state.
        :param testcase_id: testcase id to skip or None
        """
        if testcase_id:
            assert type(testcase_id) is str

        testcase_t = self.get_testcase(testcase_id)

        if testcase_t is None:
            testcase_t = self.current_tc

        if testcase_t is None:
            error_msg = "Non existent testcase: %s and non ongoing one either" % testcase_id
            raise TestSuiteError(error_msg)

        # check if testcase already in skip state
        if testcase_t.state == 'skipped':
            return

        logger.debug("Skipping testcase: %s" % testcase_t.id)

        testcase_t.change_state("skipped")

        # if skipped tc is current test case then current_tc -> None
        if self.current_tc is not None and (testcase_t.id == self.current_tc.id):
            self.current_tc = None
            logger.debug("re-referencing current testcase to None")

    def get_testcase(self, testcase_id):
        """
        :return: testcase instance or None if non existent
        """
        if testcase_id is None:
            return self.get_current_testcase()

        else:

            assert type(testcase_id) is str

            try:
                return self.teds[testcase_id]
            except KeyError:
                logger.info('testcase %s not found in list: %' % (testcase_id, self.teds.keys()))
                return None

    def get_current_testcase(self):
        try:
            return self.current_tc
        except Exception:
            return None

    def get_current_testcase_id(self):
        try:
            return self.current_tc.id
        except Exception:
            return None

    def get_current_step_id(self):
        try:
            return self.current_tc.current_step.id
        except Exception:
            return None

    def get_current_step(self):
        try:
            return self.current_tc.current_step
        except Exception:
            return None

    def get_current_step_state(self):
        try:
            return self.current_tc.current_step.state
        except Exception:
            return None

    def get_current_testcase_state(self):
        try:
            return self.current_tc.state
        except Exception:
            return None

    def get_agents_addressing_from_configurations(self):
        # attention! TD configuration addresses overwrite themselves so keep the coherence at the yaml level!
        testsuite_agents_config = {}

        for tc_conf in self.tc_configs.values():
            testsuite_agents_config.update(tc_conf.get_addressing_table())

        return testsuite_agents_config

    def get_current_testcase_configuration(self):
        try:
            return self.tc_configs[self.current_tc.configuration_id]
        except Exception:
            return None

    def get_current_testcase_configuration_id(self):
        try:
            return self.current_tc.configuration_id
        except Exception:
            return None

    def get_testcases_basic(self, verbose=None):

        tc_list = []
        for tc_v in self.teds.values():
            tc_list.append(tc_v.to_dict(verbose))
        # If no test case found
        if len(tc_list) == 0:
            raise TestSuiteError("No test cases found")

        return tc_list

    def get_testcases_list(self):
        return list(self.teds.keys())

    def set_current_testcase_state(self, state):
        assert type(state) is str
        self.current_tc.change_state(state)

    def finish_check_step(self, description, partial_verdict):

        if self.get_current_step_state() != 'executing':
            logger.warning("You cannot do this in state: %s" % self.get_current_step_state())
            return

        if self.current_tc.current_step.type != 'check':
            logger.warning("You cannot do this in state: %s" % self.current_tc.current_step.type)
            return

        assert partial_verdict.lower() in Verdict.values

        self.current_tc.current_step.set_result(partial_verdict.lower(), "CHECK step: %s" % description)
        self.current_tc.current_step.change_state('finished')

        # some info logs:
        logger.debug("[step_finished event] step %s, type %s -> new state : %s"
                     % (self.current_tc.current_step.id,
                        self.current_tc.current_step.type,
                        self.current_tc.current_step.state))

    def finish_verify_step(self, verify_response):

        if self.get_current_step_state() != 'executing':
            logger.warning("You cannot do this in state: %s" % self.get_current_step_state())
            return

        if self.current_tc.current_step.type != 'verify':
            logger.warning("You cannot do this in state: %s" % self.current_tc.current_step.type)
            return

        assert type(verify_response) is bool

        if verify_response:
            self.current_tc.current_step.set_result("pass",
                                                    "VERIFY step: User informed that the information was displayed "
                                                    "correclty on his/her IUT")
        else:
            self.current_tc.current_step.set_result("fail",
                                                    "VERIFY step: User informed that the information was not displayed"
                                                    " correclty on his/her IUT")

        self.current_tc.current_step.change_state('finished')

        # some info logs:
        logger.debug("[step_finished event] step %s, type %s -> new state : %s"
                     % (self.current_tc.current_step.id,
                        self.current_tc.current_step.type,
                        self.current_tc.current_step.state))

    def finish_stimuli_step(self):

        if self.get_current_step_state() != 'executing':
            logger.warning("You cannot do this in state: %s" % self.get_current_step_state())
            return

        if self.current_tc.current_step.type != 'stimuli':
            logger.warning("You cannot do this in state: %s"%self.current_tc.current_step.type)
            return

        self.current_tc.current_step.change_state('finished')

        # some info logs:
        logger.debug("[step_executed event] step %s, type %s -> new state : %s"
                     % (self.current_tc.current_step.id,
                        self.current_tc.current_step.type,
                        self.current_tc.current_step.state))

    def get_testcase_report(self, testcase_id=None):
        """
        Returns testcase report of provided testcase id, or current one if None is given as argument
        """

        if testcase_id:
            assert type(testcase_id) is str
        # assigns the one which is not None:
        tc = self.get_testcase(testcase_id) or self.get_current_testcase()
        return tc.report

    def reinit_testcase(self, testcase_id):
        """
        re-initialises testcase if no testcase if is provided then current testcase is re-initialized
        :param testcase_id:
        :return:
        """
        tc = self.get_testcase(testcase_id) or self.get_current_testcase()
        if tc:
            tc.reinit()

    def get_detailed_status(self):
        tc_list = []
        step_list = []
        for tc_v in self.teds.values():
            tc_list.append(tc_v.to_dict(True))
            step_list.append(tc_v.seq_to_dict(True))

        # If no test case found
        if len(tc_list) == 0:
            raise TestSuiteError("No test cases found")

        return tc_list, step_list


class Verdict:
    """

    Known verdict values are:
     - 'none': No verdict set yet
     - 'pass': The NUT fulfilled the test purpose
     - 'inconclusive': The NUT did not fulfill the test purpose but did not display
                 bad behaviour
     - 'fail': The NUT did not fulfill the test purpose and displayed a bad
               behaviour
     - 'aborted': The test execution was aborted by the user
     - 'error': A runtime error occured during the test

    At initialisation time, the verdict is set to None. Then it can be updated
    one or multiple times, either explicitly calling set_verdict() or
    implicitly if an unhandled exception is caught by the control module
    (error verdict) or if the user interrupts the test manually (aborted
    verdict).

    Each value listed above has precedence over the previous ones. This means
    that when a verdict is updated, the resulting verdict is changed only if
    the new verdict is worse than the previous one.
    """

    __values = ('none', 'pass', 'inconclusive', 'fail', 'aborted', 'error')

    def __init__(self, initial_value: str = None):
        """
        Initialize the verdict value to 'none' or to the given value

        :param initial_value: The initial value to put the verdict on
        :type initial_value: optional(str)
        """
        self.__value = 0
        self.__message = ''
        if initial_value is not None:
            self.update(initial_value)

    def update(self, new_verdict: str, message: str = ''):
        """
        Update the verdict

        :param new_verdict: The name of the new verdict value
        :param message: The message associated to it
        :type new_verdict: str
        :type message: str
        """
        assert new_verdict in self.__values

        new_value = self.__values.index(new_verdict)
        if new_value >= self.__value:
            self.__value = new_value
            self.__message = message

    @classmethod
    def values(cls):
        """
        List the known verdict values

        :return: The known verdict values
        :rtype: (str)
        """
        return cls.__values

    def get_value(self) -> str:
        """
        Get the value of the verdict

        :return: The value of the verdict as a string
        :rtype: str
        """
        return self.__values[self.__value]

    def get_message(self) -> str:
        """
        Get the last message update of this verdict

        :return: The last message update
        :rtype: str
        """
        return self.__message

    def __str__(self) -> str:
        """
        Get the value of the verdict as string for printing it

        :return: The value of the verdict as a string
        :rtype: str
        """
        return self.__values[self.__value]


class Iut:
    def __init__(self, node=None, mode="user_assisted"):
        # TODO get IUT mode from session config!!!
        self.node = node
        if mode:
            assert mode in ("user_assisted", "automated")
        self.mode = mode
        self.address = None

    def to_dict(self):
        ret = OrderedDict({'node': self.node})
        ret.update({
            'node_execution_mode': self.mode,
            'node_address': self.address
        })
        return ret

    def __repr__(self):
        if self.mode:
            return "%s(node=%s, mode=%s, address=%s)" % (
                self.__class__.__name__, self.node, self.mode if self.mode else "not defined..", self.address)
        return "%s(node=%s)" % (self.__class__.__name__, self.node)


class TestConfig:
    """
    This class is for generating objects containing a copy of the information of the test configuration yaml file
    """

    def __init__(self, configuration_id, uri, nodes, topology, addressing, description):
        self.id = configuration_id
        self.uri = uri
        self.nodes = nodes
        self.nodes_configured = set()
        self.nodes_description = description

        # list of link dictionaries, each link has link id, nodes list, and capture_filter configuring the sniffer
        # see test configuration yaml file
        self.topology = topology

        # default addressing table
        self.addressing_table = dict()
        for item in addressing:
            self.addressing_table.update(
                {
                    item['node']:
                        (
                            item['ipv6_prefix'],
                            item['ipv6_host']
                        )
                }
            )

    def __repr__(self):
        return json.dumps(self.to_dict(True))

    def update_node_address(self, node, address):
        # TODO drop these assertions later on
        assert type(node) is str
        assert type(address) is tuple
        self.addressing_table.update({node: address})
        self.nodes_configured.add(node)

    def get_nodes_on_link(self, link=None):
        nodes_on_link = []
        # let's find the target node first
        if link:
            for link_item in self.topology:
                if link_item['link_id'] == link:
                    nodes_on_link = link_item['link_id']['nodes'].copy()  # copy list

        else:  # assuming only one link defined in test configuration (YAML)
            nodes_on_link = self.topology[0]['nodes'].copy()  # copy list

        return nodes_on_link

    # TODO depricate all addresses related API calls in favour of this one
    def get_addressing_table(self):
        return self.addressing_table

    def get_node_address(self, node):
        return self.addressing_table[node]

    def get_target_address(self, node, link=None):
        """
        We assume two nodes per link:
         node & target_node

        If the test configuration defines more that one link, then link argument must be provided.

        :param node: Node origin/source of the communication
        :param link: link which is used by node to contact target_node
        :return: target address (str)
        """
        target = None
        target_node = None
        nodes_on_link = self.get_nodes_on_link(link)

        assert node in nodes_on_link, 'Node %s not in known nodes link list: %s' % (node, nodes_on_link)
        assert len(nodes_on_link) == 2
        nodes_on_link.remove(node)
        target_node = nodes_on_link.pop()

        return self.get_node_address(target_node)

    def check_all_iut_nodes_configured(self):
        return len(self.nodes_configured) == len(self.get_nodes_on_link())

    def to_dict(self, verbose=None):
        d = OrderedDict()
        d['configuration_id'] = self.id
        d['addressing_table'] = self.addressing_table

        # TODO deprecate this (returned keys of the dict should not be address_coap_client), use address table only
        # TODO deprecate sixlowpan automated iut may be using this
        for key, val in self.addressing_table.items():
            d['address_%s' % key] = "%s::%s" % val

        if verbose:
            d['configuration_ref'] = self.uri
            d['nodes'] = self.nodes
            d['topology'] = self.topology
            d['nodes_description'] = self.nodes_description

        return dict(d)


class Step():
    def __init__(self, step_id, type, description, node=None):
        self.id = step_id
        assert type in ("stimuli", "check", "verify", "feature")
        self.type = type
        self.description = description

        # stimuli and verify step MUST have a iut field in the YAML file
        if type == 'stimuli' or type == 'verify':
            assert node is not None
            self.iut = Iut(node)

            # Check and verify steps need a partial verdict
            self.partial_verdict = Verdict()
        else:
            self.iut = None

        self.state = None

    def __repr__(self):
        node = ''
        mode = ''
        if self.iut is not None:
            node = self.iut.node
            mode = self.iut.mode
        return "%s(step_id=%s, type=%s, description=%s, iut node=%s, iut execution mode =%s)" \
               % (self.__class__.__name__, self.id, self.type, self.description, node, mode)

    def reinit(self):

        if self.type in ('check', 'verify', 'feature'):
            self.partial_verdict = Verdict()

            # when using post_mortem analysis mode all checks are postponed , and analysis is done at the end of the TC
            logger.debug('Processing step init, step_id: %s, step_type: %s, ANALYSIS_MODE is %s' % (
                self.id, self.type, ANALYSIS_MODE))
            if self.type == 'check' or self.type == 'feature' and ANALYSIS_MODE == 'post_mortem':
                self.change_state('postponed')
            else:
                self.change_state(None)
        else:  # its a stimuli
            self.change_state(None)

    def to_dict(self, verbose=None):
        step_dict = OrderedDict()
        step_dict['step_id'] = self.id
        if verbose:
            step_dict['step_type'] = self.type
            step_dict['step_info'] = self.description
            step_dict['step_state'] = self.state
            # it the step is a stimuli then lets add the IUT info(note that checks dont have that info)
            if self.type == 'stimuli' or self.type == 'verify':
                step_dict.update(self.iut.to_dict())
        return step_dict

    def change_state(self, state):
        # postponed state used when checks are postponed for the end of the TC execution
        assert state in (None, 'executing', 'finished', 'postponed', 'aborted')
        self.state = state
        logger.debug('Step %s state changed to: %s' % (self.id, self.state))

    def set_result(self, result, result_info):
        # Only check and verify steps can have a result
        assert self.type in ('check', 'verify', 'feature')
        assert result in Verdict.values()
        self.partial_verdict.update(result, result_info)


class TestCase:
    """
    FSM states:
    (None,'skipped', 'configuring','executing','ready_for_analysis','analyzing','finished')
    - None -> Rest state. Wait for user input.
    - Skipped -> If a TC is in skipped state is probably cause of user input. Jump to next TC
    - Configuring -> Configuring remotes. Once all configuration.executed messages from IUTs are received (or timed-out)
        we pass to state executing
    - Executing -> Inside this state we iterate over the steps. Once iteration finished go to "Analyzing" state.
    - Analyzing -> Most probably we are waiting for TAT analysis CHECK analysis (eith post_mortem or step_by_step).
        Jump to finished once answer received and final verdict generated.
    - Finished -> all steps finished, all checks analyzed, and verdict has been emitted. Jump to next TC

    ready_for_analysis -> intermediate state between executing and analyzing for waiting for user call to analyse TC
    """

    def __init__(self, testcase_id, uri, objective, configuration, references, pre_conditions, notes, sequence):
        self.id = testcase_id
        self.state = None
        self.uri = uri
        self.objective = objective
        self.configuration_id = configuration
        self.references = references
        self.pre_conditions = pre_conditions
        self.notes = notes
        self.sequence = []
        for s in sequence:
            # some sanity checks of imported steps
            try:
                assert "step_id" and "description" and "type" in s
                if s['type'] == 'stimuli':
                    assert "node" in s
                self.sequence.append(Step(**s))
            except:
                raise TestSuiteError("Error found while trying to parse: %s" % str(s))
        self._step_it = iter(self.sequence)
        self.current_step = None
        self.report = None

        # TODO if ANALYSIS is post mortem change all check step states to postponed at init!

    def reinit(self):
        """
        - prepare test case to be re-executed
        - brings to state zero variables that might have changed during a previous execution
        :return:
        """
        self.state = None
        self.current_step = None
        self._step_it = iter(self.sequence)

        for s in self.sequence:
            s.reinit()

    def __repr__(self):
        return "%s(testcase_id=%s, uri=%s, objective=%s, configuration=%s, notes=%s, test_sequence=%s)" % (
            self.__class__.__name__, self.id,
            self.uri, self.objective, self.configuration_id, self.notes, self.sequence)

    def to_dict(self, verbose=None):

        d = OrderedDict()
        d['testcase_id'] = self.id
        d['testcase_ref'] = self.uri
        d['state'] = self.state

        if verbose:
            d['objective'] = self.objective
            d['pre_conditions'] = self.pre_conditions
            d['notes'] = self.notes

        return d

    def seq_to_dict(self, verbose=None):
        steps = []
        for step in self.sequence:
            steps.append(step.to_dict(verbose))
        return steps

    def change_state(self, state):
        assert state in (None,
                         'skipped',
                         'configuring',
                         'ready',
                         'executing',
                         'ready_for_analysis',
                         'analyzing',
                         'finished',
                         'aborted')
        self.state = state

        if state == 'skipped':
            for step in self.sequence:
                step.change_state('finished')

        logger.debug('Testcase %s changed state to %s' % (self.id, state))

    def abort(self):
        for step in self.sequence:
            if step.type in ('check', 'verify', 'feature'):
                step.set_result('aborted', 'Testcase was aborted')
            step.change_state('aborted')
        self.change_state('aborted')
        self.current_step = None

    def check_all_steps_finished(self):
        """
        Check that there are no steps in states: 'None' or 'executing'
        :return:
        """
        it = iter(self.sequence)
        step = next(it)

        try:
            while True:
                # check that there's no steps in state = None , executing or configuring
                if step.state is None \
                        or step.state == 'executing' \
                        or step.state == 'configuring' \
                        or step.state == 'ready':
                    logger.debug("[TESTCASE] - there are still steps to execute or under execution")
                    return False
                else:
                    step = it.__next__()
        except StopIteration:
            logger.debug("[TESTCASE] - all steps in TC are either finished or pending -> ready for analysis")
            return True

    def generate_testcases_verdict(self, tat_post_mortem_analysis_report=None):
        """
        Generates the final verdict of TC and report taking into account the CHECKs and VERIFYs of the testcase
        :return: tuple: (final_verdict, verdict_description, tc_report) ,
                 where final_verdict in ("None", "error", "inconclusive", "pass" , "fail")
                 where description is String type
                 where tc report is a list :
                                [(step, step_partial_verdict, step_verdict_info, associated_frame_id (can be null))]
        """
        # TODO hanlde frame id associated to the step , used for GUI purposes
        assert self.check_all_steps_finished(), "Found non finished steps: %s" % json.dumps(
            self.seq_to_dict(verbose=True))

        final_verdict = Verdict()
        tc_report = []

        if self.state == 'skipped' or self.state == 'aborted':
            return ('None', 'Testcase: %s was %s.' % (self.id, self.state), [])

        logger.debug("[VERDICT GENERATION] starting the verdict generation")
        for step in self.sequence:
            # for the verdict we use the info in the checks and verify steps
            if step.type in ("check", "verify", "feature"):

                logger.debug("[VERDICT GENERATION] Processing step %s" % step.id)

                if step.state == "postponed":
                    tc_report.append((step.id, None, "%s step: postponed" % step.type.upper(), ""))
                elif step.state == "finished":
                    tc_report.append(
                        (step.id, step.partial_verdict.get_value(), step.partial_verdict.get_message(), ""))
                    # update global verdict
                    final_verdict.update(step.partial_verdict.get_value(), step.partial_verdict.get_message())
                else:
                    msg = "step %s not ready for analysis" % (step.id)
                    logger.error("[VERDICT GENERATION] " + msg)
                    raise TestSuiteError(msg)

        # append at the end of the report the analysis done a posteriori (if any)
        if tat_post_mortem_analysis_report and len(tat_post_mortem_analysis_report) != 0:
            logger.info('Processing TAT partial verdict: ' + str(tat_post_mortem_analysis_report))
            for item in tat_post_mortem_analysis_report:
                # TODO process the items correctly
                tc_report.append(item)
                final_verdict.update(item[1], item[2])
        else:
            # we cannot emit a final verdict if the report from TAT is empy (no CHECKS-> error verdict)
            logger.info('[VERDICT GENERATION] Empty list of report passed from TAT')
            final_verdict.update('error', 'Test Analysis Tool returned an empty analysis report')

        # hack to overwrite the final verdict MESSAGE in case of pass
        if final_verdict.get_value() == 'pass':
            final_verdict.update('pass', 'No interoperability error was detected,')
            logger.debug("[VERDICT GENERATION] Test case executed correctly, a PASS was issued.")
        else:
            logger.debug("[VERDICT GENERATION] Test case executed correctly, but FAIL was issued as verdict.")
            logger.debug("[VERDICT GENERATION] info: %s' " % final_verdict.get_value())

        return final_verdict.get_value(), final_verdict.get_message(), tc_report
