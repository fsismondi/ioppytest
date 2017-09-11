# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import base64
import errno
import json
import os
import traceback
import sys
import yaml
import pika
import time
import logging

from urllib.parse import urlparse
from itertools import cycle
from collections import OrderedDict
from coap_testing_tool import AMQP_EXCHANGE, AMQP_URL
from coap_testing_tool import TMPDIR, TD_DIR, PCAP_DIR, RESULTS_DIR, AGENT_NAMES, AGENT_TT_ID, TD_COAP, TD_COAP_CFG, TD_6LOWPAN
from coap_testing_tool.utils.amqp_synch_call import publish_message, amqp_request
from coap_testing_tool.utils.rmq_handler import RabbitMQHandler, JsonFormatter
from coap_testing_tool.utils.exceptions import CoordinatorError
from coap_testing_tool.utils.event_bus_messages import *
from coap_testing_tool.agent.utils import bootstrap_agent

# TODO these VARs need to come from the session orchestrator + test configuratio files
# TODO get filter from config of the TEDs
COAP_CLIENT_IUT_MODE = 'user-assisted'
COAP_SERVER_IUT_MODE = 'automated'
ANALYSIS_MODE = 'post_mortem'  # either step_by_step or post_mortem

# if left empty => packet_sniffer chooses the loopback
# TODO send flag to sniffer telling him to look for a tun interface instead!
SNIFFER_FILTER_IF = 'tun0'

# component identification & bus params
COMPONENT_ID = 'test_coordinator'

# init logging to stnd output and log files
logger = logging.getLogger(__name__)

# default handler
sh = logging.StreamHandler()
logger.addHandler(sh)

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)
logger.setLevel(logging.INFO)

# make pika logger less verbose
logging.getLogger('pika').setLevel(logging.INFO)


# # # AUX functions # # #

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
                    ret += sub_l + ' \n '
        else:
            ret += l + ' \n '
    return ret


# # # YAML parser aux classes and methods # # #
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


yaml.add_constructor(u'!configuration', test_config_constructor)

yaml.add_constructor(u'!testcase', testcase_constructor)


# def yaml_include(loader, node):
#     # Get the path out of the yaml file
#     file_name = os.path.join(os.path.dirname(loader.name), node.value)
#
#     with open(file_name) as inputfile:
#         return yaml.load(inputfile)
#
# yaml.add_constructor("!include", yaml_include)
# yaml.add_constructor(u'!configuration', testcase_constructor)

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
        logger.debug('td_list: %s' % td_list)
    return td_list


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

    def to_dict(self):
        ret = OrderedDict({'node': self.node})
        ret.update({'node_execution_mode': self.mode})
        return ret

    # TODO implement this
    def configure(self):
        pass

    def __repr__(self):
        if self.mode:
            return "%s(node=%s, mode=%s)" % (
                self.__class__.__name__, self.node, self.mode if self.mode else "not defined..")
        return "%s(node=%s)" % (self.__class__.__name__, self.node)


class TestConfig:
    def __init__(self, configuration_id, uri, nodes, topology, description):
        self.id = configuration_id
        self.uri = uri
        self.nodes = nodes
        self.topology = topology
        self.description = description

    def __repr__(self):
        return json.dumps(self.to_dict(True))

    def to_dict(self, verbose=None):
        d = OrderedDict()
        d['configuration_id'] = self.id

        if verbose:
            d['configuration_ref'] = self.uri
            d['nodes'] = self.nodes
            d['topology'] = self.topology
            d['description'] = self.description

        return dict(d)


class Step():
    # TODO check step id uniqueness
    def __init__(self, step_id, type, description, node=None):
        self.id = step_id
        assert type in ("stimuli", "check", "verify", "feature")
        # TODO sth else might need to be defined for conformance testing TBD (inject? drop packet?)..
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
            # # it the step is a stimuli then lets add the IUT info(note that checks dont have that info)
            # if self.type == 'stimuli' or self.type == 'verify':
            #     step_dict.update(self.iut.to_dict())
        return step_dict

    def change_state(self, state):
        # postponed state used when checks are postponed for the end of the TC execution
        assert state in (None, 'executing', 'finished', 'postponed')
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
    (None,'skipped', 'executing','ready_for_analysis','analyzing','finished')
    - None -> Rest state. Wait for user input.
    - Skipped -> If a TC is in skipped state is probably cause of user input. Jump to next TC
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
                logger.error("Error found while trying to parse: %s" % str(s))
                raise
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

    def seq_to_dict(self):
        steps = []
        for step in self.sequence:
            steps.append(step.to_dict())
        return steps

    def change_state(self, state):
        assert state in (None, 'skipped', 'executing', 'ready_for_analysis', 'analyzing', 'finished')
        self.state = state

        if state == 'skipped':
            for step in self.sequence:
                step.change_state('finished')

        logger.debug('Testcase %s changed state to %s' % (self.id, state))

    def check_all_steps_finished(self):
        """
        Check that there are no steps in states: 'None' or 'executing'
        :return:
        """
        it = iter(self.sequence)
        step = next(it)

        try:
            while True:
                # check that there's no steps in state = None or executing
                if step.state is None or step.state == 'executing':
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
        assert self.check_all_steps_finished()

        final_verdict = Verdict()
        tc_report = []

        if self.state == 'skipped':
            return ('None', 'Testcase: %s was skipped.' % self.id, [])

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
                    raise CoordinatorError(msg)

        # append at the end of the report the analysis done a posteriori (if any)
        if tat_post_mortem_analysis_report and len(tat_post_mortem_analysis_report) != 0:
            logger.warning('Processing TAT partial verdict: ' + str(tat_post_mortem_analysis_report))
            for item in tat_post_mortem_analysis_report:
                # TODO process the items correctly
                tc_report.append(item)
                final_verdict.update(item[1], item[2])
        else:
            # we cannot emit a final verdict if the report from TAT is empy (no CHECKS-> error verdict)
            logger.warning('[VERDICT GENERATION] Empty list of report passed from TAT')
            final_verdict.update('error', 'Test Analysis Tool returned an empty analysis report')

        # hack to overwrite the final verdict MESSAGE in case of pass
        if final_verdict.get_value() == 'pass':
            final_verdict.update('pass', 'No interoperability error was detected,')
            logger.debug("[VERDICT GENERATION] Test case executed correctly, a PASS was issued.")
        else:
            logger.debug("[VERDICT GENERATION] Test case executed correctly, but FAIL was issued as verdict.")
            logger.debug("[VERDICT GENERATION] info: %s' " % final_verdict.get_value())

        return final_verdict.get_value(), final_verdict.get_message(), tc_report


class Coordinator:
    """
    see F-Interop API for the coordination events and services
    http://doc.f-interop.eu/#test-coordinator

    """

    # TODO decouple amqp stuff from Coordinator
    #

    def __init__(self, amqp_connection, ted_tc_file, ted_config_file):

        # configurations received after testing tool started
        self.session_config = None
        self.tc_list_requested = None

        # first let's import the TC configurations
        imported_configs = import_teds(ted_config_file)
        self.tc_configs = OrderedDict()
        for tc_config in imported_configs:
            self.tc_configs[tc_config.id] = tc_config

        logger.info('Imports: %s TC_CONFIG imported' % len(self.tc_configs))

        # lets import TCs and make sure there's a tc config for each one of them
        imported_teds = import_teds(ted_tc_file)
        self.teds = OrderedDict()
        for ted in imported_teds:
            self.teds[ted.id] = ted
            if ted.configuration_id not in self.tc_configs:
                logger.error('Missing configuration:%s for test case:%s ' % (ted.configuration_id, ted.id))
            assert ted.configuration_id in self.tc_configs

        logger.info('Imports: %s TC execution scripts imported' % len(self.teds))

        # test cases iterator (over the TC objects, not the keys)
        self._ted_it = cycle(self.teds.values())
        self.current_tc = None

        # AMQP queues and callbacks config
        self.connection = amqp_connection
        self.channel = self.connection.channel()

        self.services_q_name = 'services@%s' % COMPONENT_ID
        self.events_q_name = 'events@%s' % COMPONENT_ID

        # declare services and events queues
        self.channel.queue_declare(queue=self.services_q_name, auto_delete=True)
        self.channel.queue_declare(queue=self.events_q_name, auto_delete=True)

        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=self.services_q_name,
                                routing_key='control.testcoordination.service')

        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=self.events_q_name,
                                routing_key='control.testcoordination')

        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=self.events_q_name,
                                routing_key='control.session')

        self.channel.basic_consume(self.handle_service,
                                   queue=self.services_q_name,
                                   no_ack=False)

        self.channel.basic_consume(self.handle_control,
                                   queue=self.events_q_name,
                                   no_ack=False)

    def check_testsuite_finished(self):
        # cyclic as user may not have started by the first TC
        it = cycle(self.teds.values())

        # we need to check if we already did a cycle (cycle never raises StopIteration)
        iter_counts = len(self.teds)
        tc = next(it)

        while iter_counts >= 0:
            # check that there's no steps in state = None or executing
            if tc.state in (None, 'executing', 'ready_for_analysis', 'analyzing'):
                logger.debug("[TESTSUITE] - there is still unfinished & non-skipped test cases")
                return False
            else:  # TC state is 'skipped' or 'finished'
                tc = next(it)
            iter_counts -= 1
        if iter_counts < 0:
            logger.debug("[TESTSUITE] - Testsuite finished. No more test cases to execute.")
            return True

    def run(self):
        logger.info('start consuming events from the bus..')
        self.channel.start_consuming()

    # # # AUXILIARY AMQP MESSAGING FUNCTIONS # # #

    def notify_tun_interfaces_start(self):
        """
        Starts tun interface in agent1, agent2 and agent TT.
        This is best effort, no exeption is raised if the bootstrapping fails

        Returns:

        """
        logger.debug("Let's start the bootstrap the agents")

        # TODO get params from index.json
        agents_config = (AGENT_NAMES[0], ':1', False), (AGENT_NAMES[1], ':2', True), (AGENT_TT_ID, ':3', True)
        for agent, assigned_ip, ipv6_no_fw in agents_config:
            bootstrap_agent.bootstrap(AMQP_URL, AMQP_EXCHANGE, agent, assigned_ip, "bbbb", ipv6_no_fw)

    def notify_testcase_is_ready(self):
        if self.current_tc:
            tc_info_dict = self.current_tc.to_dict(verbose=True)

            event = MsgTestCaseReady(
                description='Next test case to be executed is %s' % self.current_tc.id,
                **tc_info_dict
            )
        else:
            event = MsgTestCaseReady(
                description='No test case selected, or no more available',
            )
        publish_message(self.channel, event)

    def notify_step_to_execute(self):
        msg_fields = {}
        msg_fields.update(self.current_tc.current_step.to_dict(verbose=True))
        msg_fields.update(self.current_tc.to_dict(verbose=False))
        if self.current_tc.current_step.iut:
            msg_fields.update(self.current_tc.current_step.iut.to_dict())

        description_message = ['Please execute step: %s \n' % self.current_tc.current_step.id]

        if self.current_tc.current_step.type == "stimuli":

            description_message += ['Step description: %s \n' % self.current_tc.current_step.description]
            if self.current_tc.current_step.iut.node:
                description_message += ['IUT: %s \n' % self.current_tc.current_step.iut.node]

            event = MsgStepStimuliExecute(
                description=description_message,
                **msg_fields
            )

        elif self.current_tc.current_step.type == "verify":

            description_message += ['Step description: %s \n' % self.current_tc.current_step.description]
            if self.current_tc.current_step.iut.node:
                description_message += ['IUT: %s \n' % self.current_tc.current_step.iut.node]

            event = MsgStepVerifyExecute(
                description=description_message,
                **msg_fields
            )
        elif self.current_tc.current_step.type == "check" or self.current_tc.current_step.type == "feature":
            raise NotImplementedError()

        publish_message(self.channel, event)

    def notify_testcase_finished(self):
        tc_info_dict = self.current_tc.to_dict(verbose=False)
        event = MsgTestCaseFinished(
            description='Testcase %s finished' % tc_info_dict['testcase_id'],
            **tc_info_dict
        )
        publish_message(self.channel, event)

    def notify_testcase_verdict(self):
        msg_fields = {}
        msg_fields.update(self.current_tc.report)
        msg_fields.update(self.current_tc.to_dict(verbose=False))
        event = MsgTestCaseVerdict(**msg_fields)
        publish_message(self.channel, event)

        # Overwrite final verdict file with final details
        json_file = os.path.join(
            RESULTS_DIR,
            self.current_tc.id + '_verdict.json'
        )
        with open(json_file, 'w') as f:
            f.write(event.to_json())

    def notify_coordination_error(self, description, error_code):

        # testcoordination.error notification
        # TODO error codes?
        coordinator_notif = OrderedDict()
        coordinator_notif.update({'description': description, })
        coordinator_notif.update({'error_code': error_code})
        coordinator_notif.update({'testsuite_status': self.states_summary()})
        err_json = json.dumps(coordinator_notif)

        logger.error('Test coordination encountered critical error: %s' % err_json)
        if self.current_tc:
            filename = self.current_tc.id + '_error.json'
        else:
            filename = 'general_error.json'

        json_file = os.path.join(
            RESULTS_DIR,
            filename

        )
        with open(json_file, 'w') as f:
            f.write(err_json)

    def notify_testsuite_finished(self):
        event = MsgTestSuiteReport(
            **self.testsuite_report()
        )
        publish_message(self.channel, event)
        json_file = os.path.join(
            RESULTS_DIR,
            'session_report.json'
        )
        with open(json_file, 'w') as f:
            f.write(event.to_json())

    def notify_current_configuration(self):
        tc_info_dict = self.current_tc.to_dict(verbose=False)
        config_id = self.current_tc.configuration_id
        config = self.tc_configs[config_id]  # Configuration object

        for desc in config.description:
            description = desc['message']
            node = desc['node']

            event = MsgTestCaseConfiguration(
                configuration_id=config_id,
                node=node,
                description=description,
                **tc_info_dict
            )
            publish_message(self.channel, event)

    def call_service_sniffer_start(self, **kwargs):

        try:
            response = amqp_request(self.connection.channel(), MsgSniffingStart(**kwargs), COMPONENT_ID)
            logger.debug("Received answer from sniffer: %s, answer: %s" % (response._type, repr(response)))
            return response
        except TimeoutError as e:
            logger.error("Sniffer API doesn't respond. Maybe it isn't up yet?")

    def call_service_sniffer_stop(self):

        try:
            response = amqp_request(self.connection.channel(), MsgSniffingStop(), COMPONENT_ID)
            logger.debug("Received answer from sniffer: %s, answer: %s" % (response._type, repr(response)))
            return response
        except TimeoutError as e:
            logger.error("Sniffer API doesn't respond. Maybe it isn't up yet?")

    def call_service_sniffer_get_capture(self, **kwargs):

        try:
            response = amqp_request(self.connection.channel(), MsgSniffingGetCapture(**kwargs), COMPONENT_ID)
            logger.debug("Received answer from sniffer: %s, answer: %s" % (response._type, repr(response)))
            return response
        except TimeoutError as e:
            logger.error("Sniffer API doesn't respond. Maybe it isn't up yet?")

    def call_service_testcase_analysis(self, **kwargs):

        request = MsgInteropTestCaseAnalyze(**kwargs)
        response = amqp_request(self.connection.channel(), request, COMPONENT_ID)
        logger.debug("Received answer from sniffer: %s, answer: %s" % (response._type, repr(response)))
        return response

    # # # API ENDPOINTS # # #

    def handle_service(self, ch, method, properties, body):

        ch.basic_ack(delivery_tag=method.delivery_tag)

        props_dict = {
            'content_type': properties.content_type,
            'delivery_mode': properties.delivery_mode,
            'correlation_id': properties.correlation_id,
            'reply_to': properties.reply_to,
            'message_id': properties.message_id,
            'timestamp': properties.timestamp,
            'user_id': properties.user_id,
            'app_id': properties.app_id,
        }
        request = Message.from_json(body)
        request.update_properties(**props_dict)

        if isinstance(request, MsgTestSuiteGetTestCases):
            testcases = self.get_testcases_basic(verbose=True)
            response = MsgTestSuiteGetTestCasesReply(
                request,
                ok=True,
                tc_list=testcases,
            )
            publish_message(self.channel, response)

        elif isinstance(request, MsgTestSuiteGetStatus):
            status = self.states_summary()
            response = MsgTestSuiteGetStatusReply(
                request,
                ok=True,
                **status
            )
            publish_message(self.channel, response)
        else:
            logger.warning('Ignoring unrecognised service request: %s' % repr(request))
            return

        logger.info('Processing request: %s' % request._type)

    def handle_control(self, ch, method, properties, body):

        ch.basic_ack(delivery_tag=method.delivery_tag)

        props_dict = {
            'content_type': properties.content_type,
            'delivery_mode': properties.delivery_mode,
            'correlation_id': properties.correlation_id,
            'reply_to': properties.reply_to,
            'message_id': properties.message_id,
            'timestamp': properties.timestamp,
            'user_id': properties.user_id,
            'app_id': properties.app_id,
        }
        event = Message.from_json(body)
        event.update_properties(**props_dict)

        logger.info('Event received: %s' % event._type)

        if isinstance(event, MsgTestCaseSkip):
            testcase_id_skip = None

            # operation health check
            if self.current_tc is None and event.testcase_id is None:
                error_msg = "No current testcase. Please provide a testcase_id to skip."
                self.notify_coordination_error(description=error_msg, error_code=None)
                return

            # set testcase_id_skip
            try:
                testcase_id_skip = event.testcase_id
                if testcase_id_skip is None:  # if {'testcase_id' : null} was sent then I skip  the current one
                    testcase_id_skip = self.current_tc.id
            except AttributeError:  # if no testcase_id was sent then I skip  the current one
                testcase_id_skip = self.current_tc.id


            # check if testcase already in skip state
            if self.get_testcase(testcase_id_skip).state == 'skipped':
                return

            # skip testcase_id_skip
            try:
                if self.skip_testcase(testcase_id_skip):  # if there's more TCs
                    self.notify_testcase_is_ready()
                elif self.check_testsuite_finished():  # no more TCs to execute
                    self.finish_testsuite()
                    self.notify_testsuite_finished()

            except Exception as e:
                self.notify_coordination_error(description=str(e), error_code=None)
                return

        elif isinstance(event, MsgTestSuiteStart):
            # lets open tun interfaces
            self.notify_tun_interfaces_start()
            time.sleep(2)

            self.start_test_suite()

            # send general notif
            self.notify_testcase_is_ready()

        elif isinstance(event, MsgTestCaseSelect):

            # assert and get testcase_id from message
            try:
                # jump to selected tc
                self.select_testcase(event.testcase_id)

            except KeyError:
                error_msg = "Incorrect or empty testcase_id"

                # send general notif
                self.notify_coordination_error(description=error_msg, error_code=None)

            except CoordinatorError as e:
                error_msg = e.description
                # send general notif
                self.notify_coordination_error(description=error_msg, error_code=None)

            # send general notif
            self.notify_testcase_is_ready()

        elif isinstance(event, MsgTestCaseStart):

            if self.current_tc is None:
                error_msg = "No testcase selected"

                # notify all
                self.notify_coordination_error(description=error_msg, error_code=None)
                return

            if self.check_testsuite_finished():
                self.notify_testsuite_finished()
            else:
                self.start_testcase()

                # send general notif
                self.notify_step_to_execute()

        elif isinstance(event, MsgStepStimuliExecuted):

            if self.current_tc is None:
                error_msg = "No testcase selected"
                # notify all
                self.notify_coordination_error(description=error_msg, error_code=None)
                return

            if self.current_tc.state is None:
                error_msg = "Test case not yet started"
                # notify all
                self.notify_coordination_error(description=error_msg, error_code=None)
                return

            if self.current_tc.current_step is None:
                error_msg = "No step under execution."
                # notify all
                self.notify_coordination_error(description=error_msg, error_code=None)
                return

            # process event only if I current step is a STIMULI
            if self.current_tc.current_step.type != 'stimuli':
                message = 'Coordination was expecting message for step type: %s , but got type: STIMULI' \
                          % (self.current_tc.current_step.type.upper())
                logger.error(message)
                self.notify_coordination_error(message, None)
                return

            self.handle_stimuli_step_executed()

            # go to next step
            if self.next_step():
                self.notify_step_to_execute()
            else:
                # im at the end of the TC:
                self.finish_testcase()
                self.notify_testcase_finished()
                self.notify_testcase_verdict()

                # there is at least a TC left
                if not self.check_testsuite_finished():
                    self.next_testcase()
                    self.notify_testcase_is_ready()

                # im at the end of the TC and also of the TS
                else:
                    self.finish_testsuite()
                    self.notify_testsuite_finished()

        elif isinstance(event, MsgStepVerifyExecuted):

            if self.current_tc is None:
                error_msg = "No testcase selected"
                # notify all
                self.notify_coordination_error(description=error_msg, error_code=None)
                return

            if self.current_tc.state is None:
                error_msg = "Test case not yet started"
                # notify all
                self.notify_coordination_error(description=error_msg, error_code=None)
                return

            if self.current_tc.current_step is None:
                error_msg = "No step under execution."
                # notify all
                self.notify_coordination_error(description=error_msg, error_code=None)
                return

            # process event only if I current step is a verify
            if self.current_tc.current_step.type != 'verify':
                message = 'Coordination was expecting message for step type: %s , but got type: VERIFY' \
                          % (self.current_tc.current_step.type.upper())
                logger.error(message)
                self.notify_coordination_error(message, None)
                return

            # assert and get testcase_id from message
            try:
                verify_response = event.verify_response
            except KeyError:
                error_msg = "Verify_response field needs to be provided"
                # send general notif
                self.notify_coordination_error(description=error_msg, error_code=None)

            self.handle_verify_step_response(verify_response)

            # go to next step
            if self.next_step():
                self.notify_step_to_execute()
            else:
                # im at the end of the TC:
                self.finish_testcase()
                self.notify_testcase_finished()
                self.notify_testcase_verdict()

                # there is at least a TC left
                if not self.check_testsuite_finished():
                    self.next_testcase()
                    self.notify_testcase_is_ready()

                # im at the end of the TC and also of the TS
                else:
                    self.finish_testsuite()
                    self.notify_testsuite_finished()

        elif isinstance(event, MsgInteropSessionConfiguration):
            tc_list_requested = []
            session_config = event.to_dict()

            logging.info(" Interop session configuration received : %s" % session_config)

            try:
                for test in event.tests:
                    test_url = urlparse(test['testcase_ref'])
                    tc_id = str(test_url.path).lstrip("/tests/")
                    tc_list_requested.append(tc_id)

            except Exception as e:
                error_msg = "Wrong message format sent for session configuration."
                self.notify_coordination_error(description=error_msg, error_code=None)
                return

            self.configure_test_suite(tc_list_requested)

            self.session_config = session_config

            event = MsgTestingToolConfigured(
                session_id=event.session_id,
                testing_tools=event.testing_tools,
                tc_list=self.get_testcases_basic(verbose=False),
            )

            publish_message(self.channel, event)

        elif isinstance(event, MsgStepCheckExecuted):

            if self.current_tc is None:
                error_msg = "No testcase selected"
                # notify all
                self.notify_coordination_error(description=error_msg, error_code=None)
                return

            if self.current_tc.state is None:
                error_msg = "Test case not yet started"
                # notify all
                self.notify_coordination_error(description=error_msg, error_code=None)
                return

            if self.current_tc.current_step is None:
                error_msg = "No step under execution."
                # notify all
                self.notify_coordination_error(description=error_msg, error_code=None)
                return

            # process event only if I current step is a check
            if self.current_tc.current_step.type != 'check':
                message = 'Coordination was expecting message for step type: %s , but got type: CHECK' \
                          % (self.current_tc.current_step.type.upper())
                logger.error(message)
                self.notify_coordination_error(message, None)
                return

            try:
                verdict = event.partial_verdict
                description = event.description
            except KeyError:
                self.notify_coordination_error(description='Malformed CHECK response', error_code=None)

            self.handle_check_step_response(verdict, description)

            # go to next step
            if self.next_step():
                self.notify_step_to_execute()
            else:
                # im at the end of the TC:
                self.finish_testcase()
                self.notify_testcase_finished()
                self.notify_testcase_verdict()

                # there is at least a TC left
                if not self.check_testsuite_finished():
                    self.next_testcase()
                    self.notify_testcase_is_ready()

                # im at the end of the TC and also of the TS
                else:
                    self.finish_testsuite()
                    self.notify_testsuite_finished()

        else:
            if event._type:
                logger.debug('Event dropped (either incorrect or "echo" event received). Event type: %s' % event._type)
            else:
                logger.error('Malformed message')

    # # # TRANSITION METHODS for the Coordinator FSM # # #

    def get_testcases_basic(self, verbose=None):

        tc_list = []
        for tc_v in self.teds.values():
            tc_list.append(tc_v.to_dict(verbose))
        # If no test case found
        if len(tc_list) == 0:
            raise CoordinatorError("No test cases found")

        return tc_list

    def get_testcases_list(self):
        return list(self.teds.keys())

    def select_testcase(self, params):
        """
        this is more like a jump to function rather than select
        :param params: test case id
        :return: current testcase object
        :raises: CoordinatorError when test case not found
        """
        tc_id = params
        if tc_id in list(self.teds.keys()):
            self.current_tc = self.teds[tc_id]
            # in case is was already executed once
            self.current_tc.reinit()
            logger.debug("Test case selected to be executed: %s" % self.current_tc.id)
            return self.current_tc
        else:
            logger.error("%s not found in : %s " % (tc_id, self.teds))
            raise CoordinatorError('Testcase not found')

    def configure_test_suite(self, tc_list_requested):
        assert tc_list_requested is not None

        # get all TCs
        tc_list_available = self.get_testcases_list()

        # verify if selected TCs are available
        tc_non_existent = list(set(tc_list_requested) - set(tc_list_available))
        tc_to_skip = list(set(tc_list_available) - set(tc_list_requested))

        if len(tc_list_requested) == 0:
            self.notify_coordination_error(
                description='No testcases selected. Using default selection: ALL',
                error_code='TBD'
            )
            return

        if len(tc_non_existent) != 0:
            self.notify_coordination_error(
                description='The following testcases are not available in the testing tool: %s'
                            % str(tc_non_existent),
                error_code='TBD'
            )

        if len(tc_to_skip) != 0:
            for item in tc_to_skip:
                self.skip_testcase(item)

        self.tc_list_requested = tc_list_requested

    def start_test_suite(self):
        """
        :return: test case to start with
        """
        # resets all previously executed TC
        for tc in self.teds.values():
            tc.reinit()

        # reconfigure test suite
        if self.tc_list_requested:
            self.configure_test_suite(self.tc_list_requested)

        if self.current_tc is None:
            self._ted_it = cycle(self.teds.values())  # so that we start back from the first
            self.next_testcase()
        return self.current_tc

    def finish_testsuite(self):
        # TODO copy json and PCAPs to results repo
        # TODO prepare a test suite report of the tescases verdicts?
        pass

    def start_testcase(self):
        """
        Method to start current tc (the previously selected tc).
        In the case current TC is none then next_testcase() is run.

        :return:
        """
        # init testcase and step and their states if they are None
        if self.current_tc is None or self.current_tc.state == 'finished':
            self.next_testcase()

        if self.current_tc.current_step is None:
            self.next_step()

        self.current_tc.change_state('executing')

        # send the configuration events to each node
        self.notify_current_configuration()

        # start sniffing each link
        # TODO this is still not handled by sniffer, for the time being sniffer only supports sniffing the tun interface
        config = self.tc_configs[self.current_tc.configuration_id]
        for link in config.topology:
            filter_proto = link['capture_filter']
            link_id = link['link_id']

            sniff_params = {
                'capture_id': self.current_tc.id[:-4],
                'filter_proto': filter_proto,
                'filter_if': SNIFFER_FILTER_IF,
                'link_id': link_id,
            }

            if self.call_service_sniffer_start(**sniff_params):
                logger.debug('Sniffer succesfully started')
            else:
                logger.error('Sniffer couldnt be started')

        return self.current_tc.current_step

    def skip_testcase(self, testcase_id):
        """

        :param testcase_id: testcase id to skip
        :return: next test case (Testcase type) to execute, None if no more testcases to execute
        """
        testcase_t = self.get_testcase(testcase_id)

        if testcase_t is None:
            error_msg = "Non existent testcase: %s" % testcase_id
            raise Exception(error_msg)

        logger.debug("Skipping testcase: %s" % testcase_t.id)

        if testcase_t.state and testcase_t.state == 'executing':
            self.call_service_sniffer_stop()

        testcase_t.change_state("skipped")

        # if skipped tc is current test case then next tc
        if self.current_tc is not None and (testcase_t.id == self.current_tc.id):
            self.next_testcase()

        return self.current_tc

    def handle_verify_step_response(self, verify_response):
        # some sanity checks on the states
        assert self.current_tc is not None
        assert self.current_tc.state is not None
        assert self.current_tc.current_step is not None
        assert self.current_tc.current_step.state == 'executing'
        assert verify_response is not None

        if verify_response is True:
            self.current_tc.current_step.set_result("pass",
                                                    "VERIFY step: User informed that the information was displayed "
                                                    "correclty on his/her IUT")
        elif verify_response is False:
            self.current_tc.current_step.set_result("fail",
                                                    "VERIFY step: User informed that the information was not displayed"
                                                    " correclty on his/her IUT")
        else:
            self.current_tc.current_step.set_result("error", 'Malformed verify response from GUI')
            raise CoordinatorError('Malformed VERIFY response')

        self.current_tc.current_step.change_state('finished')

        # some info logs:
        logger.debug("[step_finished event] step %s, type %s -> new state : %s"
                     % (self.current_tc.current_step.id,
                        self.current_tc.current_step.type,
                        self.current_tc.current_step.state))

    def handle_check_step_response(self, verdict, description):
        # some sanity checks on the states
        assert self.current_tc is not None
        assert self.current_tc.state is not None
        assert self.current_tc.current_step is not None
        assert self.current_tc.current_step.state == 'executing'

        # sanity checks on the passed params
        assert verdict is not None
        assert description is not None
        assert verdict.lower() in Verdict.values

        self.current_tc.current_step.set_result(verdict.lower(), "CHECK step: %s" % description)
        self.current_tc.current_step.change_state('finished')

        # some info logs:
        logger.debug("[step_finished event] step %s, type %s -> new state : %s"
                     % (self.current_tc.current_step.id,
                        self.current_tc.current_step.type,
                        self.current_tc.current_step.state))

    def handle_stimuli_step_executed(self):
        """
        :return: dict of the next step to be executed
        """

        # some sanity checks on the states
        assert self.current_tc is not None
        assert self.current_tc.state is not None
        assert self.current_tc.current_step is not None
        assert self.current_tc.current_step.state == 'executing'

        # step state ->finished
        self.current_tc.current_step.change_state('finished')

        # some info logs:
        logger.debug("[step_finished event] step %s, type %s -> new state : %s"
                     % (self.current_tc.current_step.id,
                        self.current_tc.current_step.type,
                        self.current_tc.current_step.state))

    def finish_testcase(self):
        """
        :return:
        """
        assert self.current_tc.check_all_steps_finished()
        self.current_tc.current_step = None

        # get TC params
        # tc_id = self.current_tc.id
        tc_id = self.current_tc.id[:-4]
        tc_ref = self.current_tc.uri

        self.current_tc.change_state('analyzing')
        # Finish sniffer and get PCAP
        logger.debug("Sending sniffer stop request...")
        self.call_service_sniffer_stop()
        time.sleep(0.2)

        if ANALYSIS_MODE == 'post_mortem':

            tat_response = None
            gen_verdict = ''
            gen_description = ''
            report = []
            error_msg = ''

            logger.debug("Sending get capture request to sniffer...")
            sniffer_response = self.call_service_sniffer_get_capture(capture_id=tc_id)

            # let's try to save the file and then push it to results repo
            try:
                if sniffer_response.ok is True:
                    pcap_file_base64 = sniffer_response.value
                    filename = sniffer_response.filename

                    # save PCAP to file
                    with open(os.path.join(PCAP_DIR, filename), "wb") as pcap_file:
                        nb = pcap_file.write(base64.b64decode(pcap_file_base64))
                        logger.debug("Pcap correctly saved (%d Bytes) at %s" % (nb, TMPDIR))

                    logger.debug("Sending PCAP file to TAT for analysis...")

                    # Forwards PCAP to TAT to get CHECKs results
                    try:
                        tat_response = self.call_service_testcase_analysis(testcase_id=tc_id,
                                                                           testcase_ref=tc_ref,
                                                                           file_enc="pcap_base64",
                                                                           filename=tc_id + ".pcap",
                                                                           value=pcap_file_base64)
                    except TimeoutError as e:
                        error_msg += "TAT didnt answer to the analysis request"
                        logger.error(error_msg)

                    if tat_response and tat_response.ok:

                        logger.info("Response received from TAT: %s " % repr(tat_response))
                        # Save the json object received
                        json_file = os.path.join(
                            TMPDIR,
                            tc_id + '_analysis.json'
                        )

                        with open(json_file, 'w') as f:
                            f.write(tat_response.to_json())

                        # let's process the partial verdicts from TAT's answer
                        # format : [[partial verdict : str, description : str]]
                        partial_verd = []
                        step_count = 0
                        for item in tat_response.partial_verdicts:
                            # let's partial verdict id
                            step_count += 1
                            p = ("post_mortem_analysis_check_%d" % step_count, item[0], item[1])
                            partial_verd.append(p)
                            logger.debug("Processing partical verdict received from TAT: %s" % str(p))

                        # generates a general verdict considering other steps partial verdicts besides TAT's
                        gen_verdict, gen_description, report = self.current_tc.generate_testcases_verdict(partial_verd)

                    else:
                        error_msg += 'Response from Test Analyzer NOK: %s' % repr(tat_response)
                        logger.warning(error_msg)
                        gen_verdict = 'error'
                        gen_description = error_msg
                        report = []
                else:
                    error_msg += 'Error encountered with packet sniffer: %s' % repr(sniffer_response)
                    logger.warning(error_msg)
                    gen_verdict = 'error'
                    gen_description = error_msg
                    report = []

            except AttributeError as ae:
                error_msg += 'Failed to process Sniffer response. Wrongly formated resonse? : %s' % repr(sniffer_response)
                logger.error(error_msg)
                gen_verdict = 'error'
                gen_description = error_msg
                report = []

            # save sent message in RESULTS dir
            final_report = OrderedDict()
            final_report['verdict'] = gen_verdict
            final_report['description'] = gen_description
            final_report['partial_verdicts'] = report

            # lets generate test case report
            self.current_tc.report = final_report

            # Save the final verdict as json
            json_file = os.path.join(
                TMPDIR,
                tc_id + '_verdict.json'
            )
            with open(json_file, 'w') as f:
                json.dump(final_report, f)

            # change tc state
            self.current_tc.change_state('finished')
            logger.info("General verdict generated: %s" % json.dumps(self.current_tc.report))

        else:
            # TODO implement step-by-step analysis
            raise NotImplementedError()

        return self.current_tc.report

    def next_testcase(self):
        """
        Circularly iterates over the testcases and returns only those which are not yet executed
        :return: current test case (Tescase object) or None if nothing else left to execute
        """

        # _ted_it is acircular iterator
        # testcase can eventually be executed out of order due tu user selection-
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

    def testsuite_report(self):
        """
        :return: list of reports
        """
        report = OrderedDict()
        for tc in self.teds.values():
            if tc.report is None:
                logger.debug("Generating dummy report for skipped testcase : %s" % tc.id)
                tc.generate_testcases_verdict(None)
            report[tc.id] = tc.report
        return report

    def next_step(self):
        """
        Simple iterator over the steps.
        Goes to next TC if current_TC is None or finished
        :return: step or None if testcase finished

        """
        if self.current_tc is None:
            self.next_testcase()
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
                summary.update(self.current_tc.current_step.to_dict())
        else:
            summary.update(
                {

                    'testcase_id': None,
                    'testcase_state': None,
                }
            )

        return summary

    def get_testcase(self, testcase_id):
        """
        :return: testcase instance or None if non existent
        """
        assert testcase_id is not None
        assert isinstance(testcase_id, str)
        try:
            return self.teds[testcase_id]
        except KeyError:
            return None
