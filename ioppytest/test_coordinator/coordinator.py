# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import os
import base64
from urllib.parse import urlparse

from transitions import Machine
from transitions.extensions.states import add_state_features, Tags, Timeout

from ioppytest import TMPDIR, PCAP_DIR, RESULTS_DIR, AMQP_URL, LOG_LEVEL, AMQP_EXCHANGE
from ioppytest.test_coordinator.amqp_connector import CoordinatorAmqpInterface
from ioppytest.test_coordinator.states_and_transitions import transitions, states
from ioppytest.test_suite.testsuite import TestSuite

from ioppytest.exceptions import CoordinatorError
from messages import *
from event_bus_utils import AmqpSynchCallTimeoutError
from event_bus_utils.rmq_handler import RabbitMQHandler, JsonFormatter

ANALYSIS_MODE = 'post_mortem'  # either step_by_step or post_mortem # TODO test suite param?

# if left empty => packet_sniffer chooses the loopback
SNIFFER_FILTER_IF = 'tun0'  # TODO test suite param?

# TODO 6lo FIX ME !
# - tun notify method -> execute only if test suite needs it (create a test suite param profiling)

# component identification & bus params
COMPONENT_ID = '%s|%s' % ('test_coordinator', 'FSM')

# init logging to stnd output and log files
logger = logging.getLogger(COMPONENT_ID)
logger.setLevel(LOG_LEVEL)

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)

# make pika and transitions loggers less verbose
logging.getLogger('pika').setLevel(logging.WARNING)
logging.getLogger('transitions').setLevel(logging.INFO)


@add_state_features(Tags, Timeout)
class CustomStateMachine(Machine):
    pass


class Coordinator(CoordinatorAmqpInterface):
    """
    Coordinator class handles event messages received from event bus, and calls the FSM triggers (state transitions).
    FSM triggers are documented in states_and_transitions.py
    """
    component_id = 'test_coordinator'

    def __init__(self, amqp_url, amqp_exchange, ted_tc_file, ted_config_file, testsuite_name):
        self.event = None
        self.testsuite_name = testsuite_name

        # testsuite init
        self.testsuite = TestSuite(ted_tc_file, ted_config_file)

        # init amqp interface
        super(Coordinator, self).__init__(amqp_url, amqp_exchange)

        self.machine = CustomStateMachine(model=self,
                                          states=states,
                                          transitions=transitions,
                                          initial='null')

    def _set_received_event(self, event=None):
        if event is None:
            logger.warning('Empty event passed to callback function')
        else:
            self.event = event

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
        self.testsuite.reinit()

    def handle_testsuite_config(self, received_event):
        session_tc_list = []
        session_id = None
        session_users = None
        session_config = None

        logging.info("Interop session configuration received : %s" % received_event)

        try:
            event_tc_list = received_event.configuration['testsuite.testcases']
            for t in event_tc_list:
                test_url = urlparse(t)
                session_tc_list.append(str(test_url.path).lstrip("/tests/"))

        except (KeyError, TypeError) as e:
            error_msg = "Empty 'testsuite.testcases' received, using as default all test cases in test description"
            logging.warning(error_msg)

        if not session_tc_list:  # this catches either None or []
            session_tc_list = self.testsuite.get_testcases_list()

        try:
            session_id = received_event.session_id
            session_users = received_event.users
            session_config = received_event.configuration
        except:
            logger.warning("Missing fields in message configuration: %s" % received_event)

        self.testsuite.configure_testsuite(session_tc_list, session_id, session_users, session_config)

    def handle_step_executed(self, received_event):
        logger.info("Handling step executed %s" % type(received_event))

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
        # agent needs an id so we can keep track of nodes id and auto-defined on manual configured address in the
        # network (e.g. forced private IPv6 address of agent)
        agent_name = None
        iut_address = None

        # TODO deprecate this MsgConfigurationExecuted (used for the 6lowpan testbed node automation)
        if type(received_event) is MsgConfigurationExecuted:
            if received_event.ipv6_address:
                # fixme this only supports bbbb::1 , bbbb::2, etc format of addresses
                iut_address = tuple(received_event.ipv6_address.split('::'))

            else:
                pass  # use default address

            agent_name = received_event.node

        elif type(received_event) is MsgAgentTunStarted:
            """ example:
            
                [Session message] [<class 'ioppytest.utils.messages.MsgAgentTunStarted'>]
                
                -----------------------  --------
                _api_version             1.0.13
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
                -----------------------  --------
        
            """

            try:
                # ipv6 tunnel, IUT destination running in another network, agent re-routes to other interface
                if received_event.re_route_packets_prefix and received_event.re_route_packets_host:
                    iut_address = received_event.re_route_packets_prefix, received_event.re_route_packets_host

                # ipv6 tunnel, IUT running hosted in same OS where agent runs
                elif received_event.ipv6_prefix and received_event.ipv6_host:
                    iut_address = received_event.ipv6_prefix, received_event.ipv6_host

                # ipv4 tunnel, IUT destination running in another network, agent re-routes to other interface
                elif received_event.ipv4_network and received_event.ipv4_host:
                    iut_address = received_event.ipv4_network, received_event.ipv4_host

                else:
                    logger.warning('Not supported agent/iut configuration: %s' % repr(received_event))
                    pass  # use default address

                agent_name = received_event.name

            except AttributeError as e:
                logger.error(e)
                raise CoordinatorError(
                    'Received a wrong formatted  agent message, update of agent source code needed? %s' % repr(
                        received_event))

        if len(iut_address) != 2:
            raise CoordinatorError('Received a wrong formatted address')

        if agent_name:
            self.testsuite.update_node_address(agent_name, iut_address)
            logger.info(
                "Agent's %s processed, updated information on IUT node: %s" % (agent_name, str(iut_address)))
        else:
            raise CoordinatorError(
                'Received a wrong formatted  agent message, update of agent source code needed? %s' % repr(
                    received_event))

        if self.testsuite.check_all_iut_nodes_configured():
            self.trigger('_all_iut_configuration_executed', None)

    def get_testcases_basic(self, verbose=None):
        tc_list = self.testsuite.get_testcases_basic(verbose)
        assert type(tc_list) is list
        return {'tc_list': tc_list}

    def get_states_summary(self):
        states = self.testsuite.states_summary()
        states.update(self.testsuite.get_testsuite_configuration())
        return states

    def get_testsuite_report(self):
        return self.testsuite.get_report()

    def get_nodes_addressing_table(self):
        return self.testsuite.get_addressing_table().copy()

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
                        tat_response = self.call_service_testcase_analysis(
                            protocol=self.testsuite_name,
                            testcase_id=tc_id,
                            testcase_ref=tc_ref,
                            file_enc="pcap_base64",
                            filename=tc_id + ".pcap",
                            value=pcap_file_base64)

                    except AmqpSynchCallTimeoutError as e:
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
                        ls_len = len(tat_response.partial_verdicts)
                        for item in tat_response.partial_verdicts:
                            # let's partial verdict id
                            step_count += 1
                            p = ("frame_check_[{}/{}]".format(step_count, ls_len), item[0], item[1])
                            partial_verd.append(p)
                            logger.debug("Processing partial verdict received from TAT: %s" % str(p))

                        # generates a general verdict considering other steps partial verdicts besides TAT's
                        gen_verdict, gen_description, report = current_tc.generate_testcases_verdict(partial_verd)

                    else:
                        error_msg += 'PCAP analysis NOK. Error message: %s (err.code: %s)' % (tat_response.error_message,
                                                                                             tat_response.error_code)
                        logger.warning(error_msg)

                        # generate verdict and verdict description
                        try:
                            gen_description = error_msg
                            gen_verdict = 'inconclusive'
                        except AttributeError:
                            gen_description = error_msg
                            gen_verdict = 'error'

                        report = []
                else:
                    error_msg += 'Error encountered with packet sniffer: %s' % repr(sniffer_response)
                    logger.warning(error_msg)
                    gen_verdict = 'error'
                    gen_description = error_msg
                    report = []

            except AttributeError as ae:
                error_msg += 'Failed to process Sniffer response. Wrongly formated response? : %s' % repr(
                    sniffer_response)
                logger.error(error_msg)
                gen_verdict = 'error'
                gen_description = error_msg
                report = []

            # TODO this should be hanlded directly by generate_testcases_verdict method
            # save sent message in RESULTS dir
            final_report = OrderedDict()
            final_report['verdict'] = gen_verdict
            final_report['description'] = gen_description
            final_report['partial_verdicts'] = report

            # TODO this should be hanlded directly by generate_testcases_verdict method
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

    def handle_testcase_restart(self, received_event):
        """
        Restarts current testcase.
        """
        current_tc_id = self.testsuite.get_current_testcase_id()
        if current_tc_id:
            self.testsuite.reinit_testcase(self.testsuite.get_current_testcase_id())
        else:
            raise CoordinatorError("No current testcase, no info on what TC to restart")

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
                logger.error("Sniffer COULDN'T be started")

    def _prepare_next_testcase(self, received_event):
        logger.info('Preparing next testcase..')

        testcase_to_execute = None

        try:
            if isinstance(received_event, MsgTestCaseSelect) or isinstance(received_event, MsgTestCaseStart):
                testcase_to_execute = self.testsuite.get_testcase(received_event.testcase_id)
                if testcase_to_execute:
                    logger.info("Event received provided test case id to execute: %s" % testcase_to_execute.id)
                    self.testsuite.go_to_testcase(testcase_to_execute.id)

            elif isinstance(received_event, MsgTestCaseRestart):
                testcase_to_execute = self.testsuite.get_current_testcase()
                logger.info("Restarting current testcase: %s" % testcase_to_execute.id)

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
        logger.info('Preparing next step..')

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


if __name__ == '__main__':
    """
    some minimal testing here.. 
    """
    default_configuration = {
        "testsuite.testcases": [
            "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
            "http://doc.f-interop.eu/tests/TD_COAP_CORE_02",
            "http://doc.f-interop.eu/tests/TD_COAP_CORE_03"
        ]
    }

    logger.setLevel(logging.DEBUG)
    from ioppytest import TD_COAP_CFG, TD_COAP

    test_coordinator = Coordinator(amqp_url=AMQP_URL,
                                   amqp_exchange=AMQP_EXCHANGE,
                                   testsuite_name='coap',
                                   ted_config_file=TD_COAP_CFG,
                                   ted_tc_file=TD_COAP)
    machine = CustomStateMachine(model=test_coordinator,
                                 states=states,
                                 transitions=transitions,
                                 initial='null')

    test_coordinator.bootstrap()
    assert test_coordinator.state == 'waiting_for_testsuite_config'

    test_coordinator.configure_testsuite(MsgSessionConfiguration(configuration=default_configuration))
    assert test_coordinator.state != 'waiting_for_testcase_start'

    test_coordinator.start_testsuite(MsgTestSuiteStart())
    assert test_coordinator.state == 'waiting_for_iut_configuration_executed'

    test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_03'))
    assert test_coordinator.state == 'waiting_for_iut_configuration_executed'

    test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_02'))
    assert test_coordinator.state == 'waiting_for_iut_configuration_executed'

    test_coordinator.select_testcase(MsgTestCaseSelect(testcase_id='TD_COAP_CORE_01'))
    assert test_coordinator.state == 'waiting_for_iut_configuration_executed'
