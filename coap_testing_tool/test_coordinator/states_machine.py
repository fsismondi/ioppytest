# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import os
import logging
import base64
from time import sleep
from urllib.parse import urlparse

from transitions import Machine
from transitions.extensions.states import add_state_features, Tags, Timeout
from transitions.core import MachineError

from coap_testing_tool import TMPDIR, TD_DIR, PCAP_DIR, RESULTS_DIR, AGENT_NAMES, AGENT_TT_ID
from coap_testing_tool.utils.amqp_synch_call import *
from coap_testing_tool.utils.event_bus_messages import *
from coap_testing_tool.utils.rmq_handler import RabbitMQHandler, JsonFormatter
from coap_testing_tool.utils.exceptions import CoordinatorError
from coap_testing_tool.test_coordinator.amqp_connector import CoordinatorAmqpInterface
from coap_testing_tool.test_coordinator.testsuite import TestSuite

# TODO these VARs need to come from the session orchestrator + test configuratio files
# TODO get filter from config of the TEDs
COAP_CLIENT_IUT_MODE = 'user-assisted'
COAP_SERVER_IUT_MODE = 'automated'
ANALYSIS_MODE = 'post_mortem'  # either step_by_step or post_mortem

# if left empty => packet_sniffer chooses the loopback
# TODO send flag to sniffer telling him to look for a tun interface instead!
SNIFFER_FILTER_IF = 'tun0'

# TODO 6lo FIX ME !
# - sniffer is handled in a complete different way (sniff amqp bus here! and not netwrosk interface using agent)
# - tun notify method -> execute only if test suite needs it (create a test suite param profiling)
# - COAP_CLIENT_IUT_MODE, COAP_SERVER_IUT_MODE , this should not exist in the code of the coord
# - change all TESTCASES_ID so they dont contain a vXX at the end,  this doesnt make any sense


# component identification & bus params
COMPONENT_ID = '%s|%s' % ('test_coordinator', 'FSM')
STEP_TIMEOUT = 300  # seconds
IUT_CONFIGURATION_TIMEOUT = 5  # seconds

# init logging to stnd output and log files
logger = logging.getLogger(COMPONENT_ID)

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


@add_state_features(Tags, Timeout)
class CustomStateMachine(Machine):
    pass


class Coordinator(CoordinatorAmqpInterface):
    component_id = 'test_coordinator'

    def __init__(self, amqp_url, amqp_exchange, ted_tc_file, ted_config_file):
        self.event = None

        # configurations received after testing tool started
        self.session_config = None
        self.tc_list_requested = None

        # testsuite init
        self.testsuite = TestSuite(ted_tc_file, ted_config_file)

        # init amqp interface
        super(Coordinator, self).__init__(amqp_url, amqp_exchange)

        machine = CustomStateMachine(model=self,
                                     states=states,
                                     transitions=transitions,
                                     initial='null')

    def _set_received_event(self, event=None):
        if event is None:
            logger.warning('Empty event passed to callback function')
        else:
            # print('[test_coordinator] >> FSM exteral event received, %s' % type(event))
            self.event = event

    # def summary(self, event=None):
    #
    # print(json.dumps(self.get_states_summary()))
    # print(self.testsuite.get_detailed_status())

    def generate_testcases_verdict(self, received_event):
        verdict_info = {}
        info1 = self.testsuite.get_current_testcase().to_dict(verbose=True)
        info2 = self.testsuite.get_testcase_report()

        verdict_info.update(info1)
        verdict_info.update(info2)

        # Overwrite final verdict file with final details
        json_file = os.path.join(
            RESULTS_DIR,
            verdict_info['testcase_id'] + '_verdict.json'
        )
        with open(json_file, 'w') as f:
            f.write(json.dumps(verdict_info))

    def configure_agent_data_plane_interfaces(self, received_event):
        # todo find a way of switching between different configuration requirements coming from each test suite
        # coap config is different from 6lowpan config
        self.notify_tun_interfaces_start(received_event)

    def handle_testsuite_start(self, received_event):
        self.testsuite.start(self.tc_list_requested)

    def handle_testsuite_config(self, received_event):
        tc_list_requested = []
        session_config = received_event.to_dict()

        logging.info(" Interop session configuration received : %s" % session_config)

        try:
            for test in received_event.tests:
                test_url = urlparse(test['testcase_ref'])
                tc_id = str(test_url.path).lstrip("/tests/")
                tc_list_requested.append(tc_id)

        except Exception as e:
            error_msg = "Wrong message format sent for session configuration."
            raise CoordinatorError(message=error_msg)

        self.testsuite.configure_test_suite(tc_list_requested)
        self.tc_list_requested = tc_list_requested
        self.session_config = session_config

    def handle_step_executed(self, received_event):

        if isinstance(received_event, MsgStepStimuliExecuted):
            self.testsuite.finish_stimuli_step()

        elif isinstance(received_event, MsgStepCheckExecuted):
            try:
                self.testsuite.finish_check_step(
                    partial_verdict=received_event.partial_verdict,
                    description=received_event.description
                )
            except AttributeError:
                raise CoordinatorError(message='Malformed CHECK response')

        elif isinstance(received_event, MsgStepVerifyExecuted):

            # assert and get testcase_id from message
            try:
                self.testsuite.finish_verify_step(
                    verify_response=received_event.verify_response
                )
            except AttributeError:
                error_msg = "Verify_response field needs to be provided"
                raise CoordinatorError(message=error_msg)

    def handle_current_step_timeout(self, received_event):
        self.testsuite.abort_current_testcase()

    def handle_iut_configuration_executed(self, received_event):
        self.testsuite.set_iut_configuration(received_event.node, received_event.ipv6_address)

        if self.testsuite.check_all_iut_nodes_configured():
            self.trigger('_all_iut_configuration_executed', None)

    def get_testcases_basic(self, verbose=None):
        tc_list = self.testsuite.get_testcases_basic(verbose)
        assert type(tc_list) is list
        return {'tc_list': tc_list}

    def get_states_summary(self):
        states = self.testsuite.states_summary()
        states.update({'tc_list': self.testsuite.get_testsuite_configuration()})
        return states

    def finish_testcase(self):
        """
        :return:
        """
        if self.testsuite.check_testcase_finished() is False:
            msg = 'expected testcase to be finished'
            logger.error(msg)
            ls_tc, ls_steps = self.testsuite.get_detailed_status()

            logger.error('testcases: %s' % ls_tc)
            logger.error('steps: %s' % ls_steps)
            raise CoordinatorError(msg)

        current_tc = self.testsuite.get_current_testcase()
        current_tc.change_state('analyzing')
        current_tc.current_step = None

        # get TC params
        tc_id = current_tc.id
        tc_ref = current_tc.uri

        # Finish sniffer and get PCAP
        logger.debug("Sending sniffer stop request...")
        self.call_service_sniffer_stop()
        time.sleep(0.5)

        # TODO break this function in smaller pieces
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
                if sniffer_response.ok:
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
                            '%s_analysis.json' % tc_id
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
                        gen_verdict, gen_description, report = current_tc.generate_testcases_verdict(partial_verd)

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
                error_msg += 'Failed to process Sniffer response. Wrongly formated resonse? : %s' % repr(
                    sniffer_response)
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
            current_tc.report = final_report

            # Save the final verdict as json
            json_file = os.path.join(
                TMPDIR,
                tc_id + '_verdict.json'
            )
            with open(json_file, 'w') as f:
                json.dump(final_report, f)

            # change tc state
            current_tc.change_state('finished')
            logger.info("General verdict generated: %s" % json.dumps(current_tc.report))

        else:
            # TODO implement step-by-step analysis
            raise NotImplementedError()

        return current_tc.report

    def handle_testcase_select(self, received_event):
        """
        this is more like a jump to function rather than select
        """
        self.testsuite.reinit_testcase(self.testsuite.get_current_testcase_id())

        # test case switch is handled by prepare_next_testcase

    def handle_testcase_skip(self, received_event):
        """
        This can skip ongoing testcases or set non-ongoing testcase into skipped state.
        """

        testcase_id_skip = None
        current_tc_id = self.testsuite.get_current_testcase_id()
        current_tc_state = self.testsuite.get_current_testcase_state()

        try:
            testcase_id_skip = received_event.testcase_id
        except AttributeError:
            pass

        if current_tc_id is None and testcase_id_skip is None:  # operation health check
            error_msg = "No ongoing testcase, nor testcase_id provided to skip."
            raise CoordinatorError(message=error_msg)

        if current_tc_id == testcase_id_skip and current_tc_state == 'executing':
            self.call_service_sniffer_stop()
            # self.to_testcase_finished(None)  # Attention ! this changes FSM state!

        # for skip_testcase() if argument is None then return current test case
        # Note that if no testcase_id is present in the received_event then I skip the current one, which is the
        # expected behaviour of this api call
        self.testsuite.skip_testcase(testcase_id_skip)

    def handle_start_testcase(self, received_event):
        """
        Method to start current tc (the previously selected tc).
        In the case current TC is none then next_testcase() is run.

        :return:
        """
        assert self.testsuite.get_current_testcase_state() in ('ready', 'configuring')
        self.testsuite.set_current_testcase_state('executing')

        # start sniffing each link
        config = self.testsuite.get_current_testcase_configuration()

        for link in config.topology:
            filter_proto = link['capture_filter']
            link_id = link['link_id']

            sniff_params = {
                'capture_id': self.testsuite.get_current_testcase_id(),
                'filter_proto': filter_proto,
                'filter_if': SNIFFER_FILTER_IF,
                'link_id': link_id,
            }

            # sniffer calls are blocking
            if self.call_service_sniffer_start(**sniff_params):
                logger.debug('Sniffer succesfully started')
            else:
                CoordinatorError('Sniffer couldnt be started')

    def _prepare_next_testcase(self, received_event):

        testcase_to_execute = None

        try:
            testcase_to_execute = self.testsuite.get_testcase(received_event.testcase_id)
            if testcase_to_execute:
                logger.info("Event received provided test case id to execute: %s" % testcase_to_execute.id)
                self.testsuite.go_to_testcase(received_event.testcase_id)
        except AttributeError:  # no testcase id provided, go to next tc
            logger.debug('No testcase id provided')
            pass

        if testcase_to_execute is None or testcase_to_execute.state == 'finished':
            testcase_to_execute = self.testsuite.next_testcase()  # advances current_tc, if None then no more TCs

        if testcase_to_execute:
            logger.info('Preparing testcase: %s' % testcase_to_execute.id)
            self.testsuite.set_current_testcase_state('configuring')
            self.trigger('_start_configuration', None)
        else:
            logger.info('No more testcases. Finishing testsuite..')
            self.trigger('_finish_testsuite', None)

    def _prepare_next_step(self, received_event):

        if self.testsuite.next_step():
            self.testsuite.set_current_testcase_state('executing')
            self.trigger('_start_next_step', None)
        else:
            self.testsuite.set_current_testcase_state('ready_for_analysis')
            self.trigger('_finish_testcase', None)

    def handle_abort_testcase(self, received_event):
        self.testsuite.abort_current_testcase()

    def is_skipping_current_testcase(self, received_event):
        try:
            tc_id = received_event.testcase_id
        except Exception as e:
            logger.debug(e)
            logger.debug('skipping current testcase %s' % tc_id)
            return True  # if no testcase if provided, then skipping current tc

        if tc_id is None:
            logger.debug('skipping current testcase %s' % tc_id)
            return True  # if testcase_id provided is None, then skipping current tc

        if tc_id == self.testsuite.get_current_testcase_id():
            logger.debug('skipping current testcase %s' % tc_id)
            return True

        logger.debug('skipping testcase different from current one')
        return False

    def handle_bootstrap(self):
        self.trigger('_bootstrapped', None)

    def handle_finish_testcase(self, received_event):
        self.finish_testcase()
        self.testsuite.set_current_testcase_state('finished')

    def handle_finish_testsuite(self, received_event):
        self.testsuite.generate_report()

        json_file = os.path.join(
            RESULTS_DIR,
            'session_report.json'
        )

        with open(json_file, 'w') as f:
            f.write(json.dumps(self.testsuite.get_report()))

            # TODO copy json and PCAPs to results repo
            # TODO prepare a test suite report of the tescases verdicts?


states = [
    {
        'name': 'null',
        'on_enter': ['bootstrap'],
        'on_exit': [],
        'tags': []
    },
    {
        'name': 'bootstrapping',
        'on_enter': ['handle_bootstrap'],
        'on_exit': ['notify_testsuite_ready'],
        'tags': ['busy']
    },
    {
        'name': 'waiting_for_testsuite_config',
        'on_enter': [],
        'on_exit': ['notify_testsuite_configured']
    },
    {
        'name': 'waiting_for_testsuite_start',
        'on_enter': [],
        'on_exit': ['notify_testsuite_started']
    },
    {
        'name': 'preparing_next_testcase',  # dummy state used for factorizing several transitions
        'on_enter': ['_prepare_next_testcase'],
        'on_exit': []
    },
    {
        'name': 'waiting_for_iut_configuration_executed',
        'on_enter': [],  # do not notify here, we will enter this state least two times
        'on_exit': [],
        'timeout': IUT_CONFIGURATION_TIMEOUT,
        'on_timeout': '_timeout_waiting_iut_configuration_executed'
    },
    {
        'name': 'waiting_for_testcase_start',
        'on_enter': ['notify_testcase_ready'],
        'on_exit': []
    },
    {
        'name': 'preparing_next_step',  # dummy state used for factorizing several transitions
        'on_enter': ['_prepare_next_step'],
        'on_exit': []
    },
    {
        'name': 'waiting_for_step_executed',
        'on_enter': ['notify_step_execute'],
        'on_exit': [],
        'timeout': STEP_TIMEOUT,
        'on_timeout': '_timeout_waiting_step_executed'
    },
    {
        'name': 'testcase_finished',
        'on_enter': [
            'notify_testcase_finished',
            'generate_testcases_verdict',
            'notify_testcase_verdict',
            'to_preparing_next_testcase'],  # jumps to following state, this makes testcase_finished a transition state
        'on_exit': []
    },
    {
        'name': 'testcase_aborted',
        'on_enter': ['notify_testcase_aborted'],
        'on_exit': []
    },
    {
        'name': 'testsuite_finished',
        'on_enter': ['handle_finish_testsuite',
                     'notify_testsuite_finished',
                     ],
        'on_exit': []
    },
]
transitions = [
    {
        'trigger': 'bootstrap',
        'source': 'null',
        'dest': 'bootstrapping'
    },
    {
        'trigger': '_bootstrapped',
        'source': 'bootstrapping',
        'dest': 'waiting_for_testsuite_config'
    },
    {
        'trigger': 'configure_testsuite',
        'source': 'waiting_for_testsuite_config',
        'dest': 'waiting_for_testsuite_start',
        'before': [
            '_set_received_event',
            'handle_testsuite_config'
        ]
    },
    {
        'trigger': 'start_testsuite',
        'source': ['waiting_for_testsuite_start',
                   'waiting_for_testsuite_config'],
        'dest': 'preparing_next_testcase',
        'before': [
            '_set_received_event',
            'handle_testsuite_start',
            'configure_agent_data_plane_interfaces'
        ]
    },
    {
        'trigger': '_start_configuration',
        'source': 'preparing_next_testcase',
        'dest': 'waiting_for_iut_configuration_executed',
        'after': 'notify_tescase_configuration'
    },
    {
        'trigger': '_finish_testsuite',
        'source': 'preparing_next_testcase',
        'dest': 'testsuite_finished',
    },
    {
        'trigger': 'iut_configuration_executed',
        'source': '*',
        'dest': '=',
        'before': ['_set_received_event'],
        'after': ['handle_iut_configuration_executed']
    },
    {
        'trigger': 'start_testcase',
        'source': [
            'waiting_for_testcase_start',
            'waiting_for_iut_configuration_executed'  # start tc and skip iut configuration executed is allowed
        ],
        'dest': 'preparing_next_step',
        'before': [
            '_set_received_event',
            'handle_start_testcase'
        ],
        'after': [
            'notify_testcase_started'
        ]
    },
    {
        'trigger': '_start_next_step',
        'source': 'preparing_next_step',
        'dest': 'waiting_for_step_executed',
    },
    {
        'trigger': '_finish_testcase',
        'source': 'preparing_next_step',
        'dest': 'testcase_finished',
        'before': [
            '_set_received_event',
            'handle_finish_testcase'
        ]
    },
    {
        'trigger': 'abort_testcase',
        'source': [
            'waiting_for_iut_configuration_executed',
            'preparing_next_step',
            'waiting_for_testcase_start',
            'waiting_for_step_executed',
        ],
        'dest': 'preparing_next_testcase',
        'before': [
            '_set_received_event',
            'handle_abort_testcase'
        ]
    },
    {
        'trigger': 'step_executed',
        'source': 'waiting_for_step_executed',
        'dest': 'preparing_next_step',
        'before': [
            '_set_received_event',
            'handle_step_executed'
        ],
    },
    {
        'trigger': '_timeout_waiting_iut_configuration_executed',
        'source': 'waiting_for_iut_configuration_executed',
        'dest': 'waiting_for_testcase_start',
        'before': '_set_received_event'
    },
    {
        'trigger': '_all_iut_configuration_executed',
        'source': 'waiting_for_iut_configuration_executed',
        'dest': 'waiting_for_testcase_start',
        'before': '_set_received_event'
    },
    {
        'trigger': '_timeout_waiting_step_executed',
        'source': 'waiting_for_step_executed',
        'dest': 'waiting_for_testsuite_start',
        'before': [
            '_set_received_event',
            'handle_current_step_timeout'
        ]
    },
    {
        'trigger': 'select_testcase',
        'source': [
            'waiting_for_iut_configuration_executed',
            'waiting_for_testcase_start',
            'waiting_for_step_executed',
            'testcase_finished'
        ],
        'dest': 'preparing_next_testcase',
        'before': [
            '_set_received_event',
            'handle_testcase_select'
        ]
    },

    {
        'trigger': 'skip_testcase',
        'source': [
            'waiting_for_iut_configuration_executed',
            'waiting_for_testcase_start',
            'waiting_for_testsuite_config'
            'waiting_for_step_executed',
            'testcase_finished'
        ],
        'dest': '=',
        'unless': 'is_skipping_current_testcase',
        'before': [
            '_set_received_event',
            'handle_testcase_skip'
        ]
    },
    {
        'trigger': 'skip_testcase',
        'source': [
            'waiting_for_iut_configuration_executed',
            'waiting_for_testcase_start',
            'waiting_for_step_executed',
            'testcase_finished'
        ],
        'dest': 'preparing_next_testcase',
        'conditions': 'is_skipping_current_testcase',
        'before': [
            '_set_received_event',
            'handle_testcase_skip'
        ]
    },
    {
        'trigger': 'go_to_next_testcase',
        'source': [],
        'dest': '=',
        'before': '_set_received_event'
    },
]

if __name__ == '__main__':
    """
    select testcases, then skip all
    """
    logger.setLevel(logging.DEBUG)
    from coap_testing_tool import TD_COAP_CFG, TD_COAP

    test_coordinator = Coordinator(amqp_url=AMQP_URL,
                                   amqp_exchange=AMQP_EXCHANGE,
                                   ted_config_file=TD_COAP_CFG,
                                   ted_tc_file=TD_COAP)
    machine = CustomStateMachine(model=test_coordinator,
                                 states=states,
                                 transitions=transitions,
                                 initial='null')

    test_coordinator.bootstrap()
    assert test_coordinator.state == 'waiting_for_testsuite_config'

    test_coordinator.configure_testsuite(MsgInteropSessionConfiguration())
    assert test_coordinator.state != 'waiting_for_testcase_start'

    test_coordinator.start_testsuite(MsgTestSuiteStart())
    assert test_coordinator.state == 'waiting_for_iut_configuration_executed'

    test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_03'))
    assert test_coordinator.state == 'waiting_for_iut_configuration_executed'

    test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_02'))
    assert test_coordinator.state == 'waiting_for_iut_configuration_executed'

    test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_01'))
    assert test_coordinator.state == 'waiting_for_iut_configuration_executed'
