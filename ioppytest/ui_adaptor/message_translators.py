#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pika
import pprint
import logging
import textwrap
import datetime
import traceback

from ioppytest import LOG_LEVEL, LOGGER_FORMAT, TD_WOT_CFG
from ioppytest.test_suite import testsuite
from messages import *
from event_bus_utils import publish_message
from event_bus_utils.rmq_handler import RabbitMQHandler, JsonFormatter
from tabulate import tabulate
from ioppytest.ui_adaptor.ui_tasks import (get_field_keys_from_ui_reply,
                                           get_current_users_online,
                                           get_field_keys_from_ui_request,
                                           get_field_value_from_ui_reply)
from ioppytest.ui_adaptor.tt_tasks import bootstrap_all_tun_interfaces

from ioppytest.ui_adaptor.user_help_text import *
from ioppytest.ui_adaptor.message_rendering import list_to_str
from ioppytest.ui_adaptor import (COMPONENT_ID,
                                  STDOUT_MAX_TEXT_LENGTH,
                                  STDOUT_MAX_TEXT_LENGTH_PER_LINE,
                                  STDOUT_MAX_STRING_LENGTH_KEY_COLUMN,
                                  STDOUT_MAX_STRING_LENGTH_VALUE_COLUMN,
                                  UI_TAG_AGENT_CONNECT,
                                  UI_TAG_AGENT_REQUIREMENTS,
                                  UI_TAG_AGENT_INSTALL,
                                  UI_TAG_AGENT_TEST,
                                  UI_TAG_AGENT_INFO,
                                  UI_TAG_SETUP,
                                  UI_TAG_REPORT,
                                  UI_TAG_VPN_STATUS)

# init logging to stnd output and log files
logger = logging.getLogger("%s|%s" % (COMPONENT_ID, 'msg_translator'))
logger.setLevel(LOG_LEVEL)

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)

TESTING_TOOL_AGENT_NAME = 'agent_TT'


@property
def NotImplementedField(self):
    raise NotImplementedError

# IMPORTANT! the following module methods create their own connections instead of re-using main thread's
# this is expensive in resources so use a little as possible!


def send_start_test_suite_event():
    con = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    ui_request = MsgTestSuiteStart()
    print("publishing .. %s" % repr(ui_request))
    publish_message(con, ui_request)
    con.close()


def send_to_ui_confirmation_request(amqp_connector, user='all', ui_msg="Confirm to continue",ui_tag={"tbd": ""}):

    req = MsgUiRequestConfirmationButton(
        tags=ui_tag,
        fields=[
            {
                "type": "p",
                "value": ui_msg,
            },
            {
                "name": "confirm",
                "type": "button",
                "value": True
            },
        ]
    )
    req.routing_key = req.routing_key.replace('all', user)
    req.reply_to = req.reply_to.replace('all', user)

    resp_confirm_agent_up = None

    try:
        resp_confirm_agent_up = amqp_connector.synch_request(
            request=req,
            timeout=300,
        )
    except Exception:  # fixme import and hanlde AmqpSynchCallTimeoutError only
        pass

    return resp_confirm_agent_up


def send_vpn_join_help_to_user(vpn_agents: dict, user='all'):

    con = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

    # lets give UI an exmple of command with the info que can directly copy and paste in terminal
    cmd_agent_example = "(!) Amount of devices in VPN has reached it's maximum"

    for name, params in vpn_agents.items():
        if params[2] is None:
            cmd_agent_example = help_agent_run_for_raw_ip_single_entry.format(
                agent_name=name,
                ipv6_prefix=params[0],
                ipv6_host=params[1])
            break

    disp = MsgUiDisplay(
        tags=UI_TAG_AGENT_CONNECT,
        fields=[
            {
                "type": "p",
                "value": env_vars_export
            },

            {
                "type": "p",
                "value": "### Run agent\n"
            },

            {
                "type": "p",
                "value": "Please run agent with (use one of the none used entries from table), e.g.:\n"
            },

            {
                "type": "p",
                "value": "`{command}`".format(command=cmd_agent_example)
            },

            {
                "type": "p",
                "value": tabulate(_get_vpn_table_representation(vpn_agents), tablefmt="grid", headers="firstrow")
            },


        ]
    )

    disp.routing_key = disp.routing_key.replace('all', user)
    publish_message(con, disp)
    con.close()


def _get_vpn_table_representation(vpn_agents):
    table = [('agent_name', 'agent_ipv6', 'last_connection')]
    for agent_name, agent_params in vpn_agents.items():
        table.append(
            (
                str(agent_name),
                "{}::{}".format(agent_params[0], agent_params[1]),
                str(agent_params[2]) if agent_params[2] else "n/a (still not used)"
            )
        )

    return table


class GenericBidirectonalTranslator(object):
    """
    This class acts as a transformation filter between TT messages and UI messages, and as a UI messages
    creator for certain generic session user actions.

                        _______________________
                        |                      |
    UI from/to messages |                      |   TT from/to messages
    <----------------   |   BiDict translator  |    <----------------
    ---------------->   |                      |    ---------------->
                        |______________________|


    This component is stateful, it saves all pending request already sent to UI,
    so then UI replies can be translated into TT chained actions.
    It also preserves some states related to the testcase and step under execution.

    --------------------------------------------------------------------------
    for simple UI message display like the one generated by <testcase verdict>
    --------------------------------------------------------------------------
     UI            Translator          TT
     |                |                |
     |                |   TT_x         |
     |                |<----------------
     |                |                |
     |       UI_x     |                |
     <----------------|                |
     |                |                |


    -----------------------------------------------------------------
     for chained actions like the one triggered by <stimuli execute>
    -----------------------------------------------------------------
     UI            Translator          TT
     |                |                |
     |                |   TT_x         |
     |                |<----------------
     |                |                |
     |      (prepare UI_x request)     |
     |     (save (UI_x,TT_x) request)  |
     |                |                |
     |       UI_x     |                |
     <----------------|                |
     |                |                |
     |  UI_y reply    |                |
     ---------------->|                |
     |                |                |
     |   (prepare TT_y chained message |
     |      using (UI_y,UI_x,TT_x))    |
     |                |                |
     |  (drop UI_y,UI_x,TT_x entry)    |
     |                |                |
     |                |   TT_y         |
     |                |---------------->
     |                |                |
     |                |                |
     |                |                |


    Request format:
        MsgUiRequestConfirmationButton(fields = [
            {
                'value': True,
                'type': 'button',
                'name': 'skip_test_case'
            }
            (...)
        ]

        Reply format:
        Message(fields = [
            {
                'skip_test_case': True
            },
            (..)
        ]

    """

    IUT_ROLES = NotImplementedField

    def __init__(self):

        logger.info("Starting UI message translator..")

        self._current_tc = None
        self._current_step = None
        self._report = None
        self._pending_responses = {}

        self.session_history_messages_types_to_save = [
            MsgSniffingGetCaptureReply,
            MsgTestCaseVerdict,
            MsgTestSuiteReport
        ]

        self.session_history_messages = []

        self.specialized_visualization = {

            # test suite /test cases /test steps messages
            MsgTestingToolReady: self._get_ui_message_highlighted_description,
            MsgTestCaseFinished: self._get_ui_message_highlighted_description,
            MsgTestCaseReady: self._get_ui_testcase_ready,
            MsgStepStimuliExecute: self._get_ui_message_steps,
            MsgStepStimuliExecuted: self._get_ui_message_highlighted_description,
            MsgStepVerifyExecute: self._get_ui_message_steps,
            MsgStepVerifyExecuted: self._get_ui_message_highlighted_description,
            MsgConfigurationExecute: self._get_ui_testcase_configure,
            MsgTestCaseSkip: self._get_ui_testcase_skip,
            MsgRoutingStartLossyLink: self._get_ui_lossy_context,

            # info
            MsgTestSuiteGetTestCasesReply: self._get_ui_testcases_list,
            MsgTestingToolConfigured: self._get_ui_testing_tool_configured,
            MsgSessionConfiguration: self._get_ui_session_configuration,

            # verdicts and results
            MsgTestCaseVerdict: self._get_ui_testcase_verdict,
            MsgTestSuiteReport: self._get_ui_test_suite_results,

            # important messages
            MsgTestingToolTerminate: self._get_ui_message_highlighted_description,

            # agents data messages and dissected messages
            MsgPacketInjectRaw: self._get_ui_packet_raw,
            MsgPacketSniffedRaw: self._get_ui_packet_raw,
            MsgDissectionAutoDissect: self._get_ui_packet_dissected,

            # tagged as debugging
            MsgSessionLog: self._get_ui_as_debug_messages,
            MsgTestingToolComponentReady: self._get_ui_as_debug_messages,
            MsgAgentTunStarted: self._get_ui_agent_messages,

            # barely important enough to not be in the debugging
            MsgTestingToolComponentShutdown: self._get_ui_message_description_and_component,
            MsgTestCaseStarted: self._get_ui_message_highlighted_description,
            MsgTestCaseStart: self._get_ui_message_highlighted_description,
            MsgTestSuiteStarted: self._get_ui_message_highlighted_description,
            MsgTestSuiteStart: self._get_ui_message_highlighted_description,
            MsgConfigurationExecuted: self._get_ui_message_highlighted_description,
        }

        self.tt_to_ui_message_translation = {
            # MsgTestingToolConfigured: self._ui_request_testsuite_start, let the user bootstrap this process
            MsgTestCaseReady: self._ui_request_testcase_start,
            MsgStepStimuliExecute: self._ui_request_step_stimuli_executed,
            MsgStepVerifyExecute: self._ui_request_step_verification,
            MsgTestCaseVerdict: self._ui_request_testcase_restart,  # this is an optional action, user may ignore it
        }

        self.ui_to_tt_message_translation = {
            'ts_start': self.get_tt_message_testsuite_start,
            'ts_abort': self.get_tt_message_testsuite_abort,
            'tc_start': self.get_tt_message_testcase_start,
            'tc_restart': self.get_tt_message_testcase_restart,
            'tc_skip': self.get_tt_message_testcase_skip,
            # 'tc_list': self._handle_get_testcase_list,
            'restart_testcase': self.get_tt_message_testcase_restart_last_executed,
            'verify_executed': self.get_tt_message_step_verify_executed,
            'stimuli_executed': self.get_tt_message_step_stimuli_executed,
        }

    def bootstrap(self, amqp_connector):
        """
        Bootstrap is executed before the main thread enters the main loop.
        During bootstrap phase the class gets to update all its configuration by asking the user directly
        (or to GUI services).

        Only during bootstrap Translators are allowed to send and receive messages directly, this is why
        bootstrap receives amqp_connector as param.
        Every child class should implement this, at least for printing a Hello World message in GUI!

        only the following API calls should be used from bootstrap method:
            amqp_connector.synch_request(self, request, timeout)
            amqp_connector.publish_ui_display(self, message: Message, user_id=None, level=None)

        """

        # for specialized request, displays etc for each type of test suite
        self._bootstrap(amqp_connector)

    def _bootstrap(self, amqp_connector):
        """
        to be implemented by child class  (if no bootstrap need then just "pass"
        """

        raise NotImplementedError()

    def get_iut_roles(self):
        return self.IUT_ROLES

    def callback_on_new_users_in_the_session(self, amqp_connector, new_user_list):
        pass  # should be re-implemented by the child -testsuite specialized- class

    def update_state(self, message):
        """
            Updates message factory states, every received message needs to be passed to this method
        """
        try:
            if message.testcase_id:
                self._current_tc = message.testcase_id
        except AttributeError:
            pass

        try:
            if message.step_id:
                self._current_step = message.step_id
        except AttributeError:
            pass

        if type(message) in self.session_history_messages_types_to_save:
            self.session_history_messages.append(message)
            logger.info('Saving message %s into session history' % repr(message))
        else:
            logger.info('Message type %s not into %s session history message types' % (
                type(message), pprint.pformat(self.session_history_messages_types_to_save)))

        # print states table
        status_table = list()
        status_table.append(['current testcase id', 'current test step id'])
        status_table.append([self._current_tc, self._current_step])

        logger.info("\n%s" % tabulate(
            tabular_data=status_table,
            tablefmt="grid",
            headers="firstrow"))

        data = [['session message history message type']]
        for i in self.session_history_messages:
            data.append([repr(i)[:STDOUT_MAX_TEXT_LENGTH_PER_LINE]])
        logger.info("\n%s" % tabulate(tabular_data=data,
                                      tablefmt="grid",
                                      headers="firstrow"))

    def tag_message(self, msg):
        """
            Updates message tags of message before being sent to UI. Every message to UI needs to be passed to this
            method before being published
        """
        if msg and not msg.tags:

            if self._current_tc:
                msg.tags = {"testcase": self._current_tc}

            else:
                msg.tags = {"logs": ""}

        return msg

    def truncate_if_text_too_long(self, msg):

        """
            Updates message body text of message before being sent to UI.
            method before being published
        """

        if msg:
            try:
                new_fields_list = []
                for f in msg.fields:
                    try:

                        if f["type"] == "p" and len(f["value"]) > STDOUT_MAX_TEXT_LENGTH:  # text too long
                            f["value"] = f["value"][:STDOUT_MAX_TEXT_LENGTH]
                            new_fields_list.append(
                                {
                                    "type": f["type"],
                                    "value": f["value"]
                                }
                            )

                            new_fields_list.append(
                                {
                                    "type": f["type"],
                                    "value": "(WARNING: this message has been truncated)"
                                }
                            )
                        else:  # not markdown, or markdown & accepted length
                            new_fields_list.append(f)

                    except KeyError:  # this is not text
                        new_fields_list.append(f)

                msg.fields = new_fields_list

            except AttributeError:
                logging.error("UI Message doesnt contain FILDS field")

        return msg

    def get_ui_request_action_message(self, message_from_tt: Message):
        """
        translates:  (message_from_tt) -> a UI request
        :returns Message for UI or None
        """

        try:
            action = self.tt_to_ui_message_translation[type(message_from_tt)]
            ui_request_message = action(message_from_tt)
            return ui_request_message

        except KeyError:
            logger.debug("Action %s not found in tt_to_ui translation table" % repr(message_from_tt))
            return None

    def translate_ui_to_tt_message(self, reply_received_from_ui):
        """
        translates:  (ui reply , pending responses info) -> a TT response
        :returns Message for TT or None

        """

        # get table entry inserted on UI request
        ui_requested_fields, ui_request_message, tt_message = self.pop_pending_response(
            reply_received_from_ui.correlation_id
        )

        # what happens if user reply has to fields? this still is not used/nor forseen to be used by this TT
        response_fields_names = get_field_keys_from_ui_reply(reply_received_from_ui)
        if len(response_fields_names) > 1:
            raise Exception("UI returned a reply with two or more fields : %s " % reply_received_from_ui.fields)

        # get that one reply field (e.g. ts_start)
        user_input_action = response_fields_names[0]

        # assert the reply field sent by UI matches the info in the pending response list
        assert user_input_action in ui_requested_fields, "%s not in %s" % (user_input_action, ui_requested_fields)

        # get the value of the field from reply_received_from_ui
        user_input_value = get_field_value_from_ui_reply(reply_received_from_ui, user_input_action)

        try:
            # get handler based on the ui response action (e.g. ts_start, tc_skip , etc)
            ui_to_tt_message_translator_func = self.ui_to_tt_message_translation[user_input_action]

            # run handler with user reply value + tt message that triggered the UI request in the first place
            message_for_tt = ui_to_tt_message_translator_func(user_input_value, tt_message)
        except KeyError:
            logger.debug(
                "No chained action to reply %s" % repr(reply_received_from_ui)[:STDOUT_MAX_TEXT_LENGTH_PER_LINE])
            return None

        logger.debug("UI reply :%s translated into TT message %s"
                     % (
                         repr(reply_received_from_ui),
                         repr(message_for_tt)
                     ))
        return message_for_tt

    def translate_tt_to_ui_message(self, message: Message):
        msg_ret = None

        # search for specialized visualization, returns fields
        if type(message) in self.specialized_visualization:
            specialized_visualization_handler = self.specialized_visualization[type(message)]

            if specialized_visualization_handler: #  message_translators may dereference some handlers on purpose
                msg_ret = specialized_visualization_handler(message)
            else:
                logger.warning("UI handler for message %s appears is %s" % (type(message),
                                                                            specialized_visualization_handler))
        else: # generic message visualization (message as a table)
            logger.info("No specialized UI visualisation for message type: %s" % str(type(message)))
            msg_ret = self._get_ui_message_as_table(message)

        if msg_ret:
            msg_ret = self.tag_message(msg_ret)
            msg_ret = self.truncate_if_text_too_long(msg_ret)

        return msg_ret

    @classmethod
    def transform_string_to_ui_markdown_display(cls, text=None):

        msg = MsgUiDisplayMarkdownText()

        fields = [
            {
                'type': 'p',
                'value': text
            }
        ]

        msg.fields = fields

        return msg

    def add_pending_response(self, corr_id, ui_requested_field_name_list: list, ui_request_message,
                             tt_request_originator):
        """
        Adds pending response to table. Note that this overwrites entries with same corr_id
        :param corr_id: Correlation id of request/reply
        :param ui_requested_field_name_list: The list of fields names in the UI request
        :param ui_request_message: Message request sent to UI
        :param ui_request_message: Message (from TT) originating the request in the first place
        :return:

        """
        if corr_id in self._pending_responses:
            logger.warning(
                "Overwriting pending response table entry, adding corr id %s | entry %s" %
                (
                    corr_id,
                    self._pending_responses[corr_id]
                )
            )

        self._pending_responses[corr_id] = ui_requested_field_name_list, ui_request_message, tt_request_originator

        logger.info(
            "Updated pending response table,adding \n\tcorr id %s \n\tentry %s"
            % (
                corr_id,
                self._pending_responses[corr_id]
            )
        )

        self.print_table_of_pending_responses()

    def print_table_of_pending_responses(self):
        # table's header
        table = [
            ['Correlation Id',
             'Field name request (list)',
             'Message sent to UI',
             'Message from TT triggering request']
        ]
        for key, value in self._pending_responses.items():
            entry = [
                key,
                value[0],
                repr(type(value[1])),
                repr(type(value[2])),
            ]
            table.append(entry)

        logger.info(tabulate(table, tablefmt="grid", headers="firstrow"))

    def get_pending_messages_correlation_id(self):
        return list(self._pending_responses.keys())

    def pop_pending_response(self, correlation_id):
        ret = None

        if correlation_id in self._pending_responses:
            ret = self._pending_responses.pop(correlation_id, None)

        logger.debug("Updated pending response table")
        self.print_table_of_pending_responses()
        return ret

    def is_pending_response(self, message):
        try:
            return message.correlation_id in self._pending_responses
        except AttributeError:
            return False

    # # # # # # #  TT -> UI translation to be implemented BY CHILD CLASS # # # # # # #

    def _ui_request_testsuite_start(self, message_from_tt):
        raise NotImplementedError()

    def _ui_request_testcase_start(self, message_from_tt):
        raise NotImplementedError()

    def _ui_request_step_verification(self, message_from_tt):
        raise NotImplementedError()

    def _ui_request_testcase_restart(self, message_from_tt):
        raise NotImplementedError()

    def _ui_request_step_stimuli_executed(self, message_from_tt):
        raise NotImplementedError()

    # # # # # # #  UI -> TT translation to be implemented BY CHILD CLASS # # # # # # #

    def get_tt_message_testsuite_start(self, user_input, origin_tt_message=None):
        raise NotImplementedError()

    def get_tt_message_testsuite_abort(self, user_input, origin_tt_message=None):
        raise NotImplementedError()

    def get_tt_message_testcase_start(self, user_input, origin_tt_message=None):
        raise NotImplementedError()

    def get_tt_message_testcase_restart(self, user_input, origin_tt_message=None):
        raise NotImplementedError()

    def get_tt_message_testcase_skip(self, user_input, origin_tt_message=None):
        raise NotImplementedError()

    def get_tt_message_step_verify_executed(self, user_input, origin_tt_message=None):
        raise NotImplementedError()

    def get_tt_message_step_stimuli_executed(self, user_input, origin_tt_message=None):
        raise NotImplementedError()

    def get_tt_message_testcase_restart_last_executed(self, user_input, origin_tt_message=None):
        raise NotImplementedError()

    # # # # # # # # # # # GENERIC MESSAGE UI VISUALISATION # # # # # # # # # # # # # # #

    def _get_ui_message_as_table(self, message):

        msg_ret = MsgUiDisplayMarkdownText()

        # convert message to table
        d = message.to_dict()
        table = []
        for key, value in d.items():
            if type(value) is list:
                flatten_value = list_to_str(value)
                flatten_value = textwrap.fill(flatten_value, width=STDOUT_MAX_STRING_LENGTH_VALUE_COLUMN)
                temp = [key, flatten_value]
            else:
                temp = [key, str(value)]
            table.append(temp)

        # prepare fields
        msg_ret.fields = [{
            'type': 'p',
            'value': tabulate(table, tablefmt="grid")
        }]

        return msg_ret

    # # # # # # # # # # # PERSONALIZED MESSAGES VISUALISATION # # # # # # # # # # # # # # #
    def _generate_ui_fields_for_testcase_report(self, tc_report: dict):
        """
        used to display in UI MsgTestCaseVerdict and MsgTestSuiteReports messages

        example:
        ------------------------------------------------------------------------------------------------------------------------
        routing_key : testsuite.testcase.verdict
        ------------------------------------------------------------------------------------------------------------------------
        {
            "_api_version": "1.0.10",
            "description": "premature end of conversation",
            "objective": "Perform GET transaction(CON mode)",
            "partial_verdicts": [
                [
                    "TD_COAP_CORE_01_step_02",
                    null,
                    "CHECK step: postponed",
                    ""
                ],
                [
                    "TD_COAP_CORE_01_step_03",
                    null,
                    "CHECK step: postponed",
                    ""
                ],
                [
                    "TD_COAP_CORE_01_step_04",
                    "pass",
                    "VERIFY step: User informed that the information was displayed correclty on his/her IUT",
                    ""
                ],
                [
                    "tat_check_1",
                    "pass",
                    "<Frame   3: [bbbb::1 -> bbbb::2] CoAP [CON 324] GET /test> Match: CoAP(type=0, code=1)"
                ],
                [
                    "tat_check_2",
                    "inconclusive",
                    "premature end of conversation"
                ]
            ],
            "pre_conditions": [
                "Server offers the resource /test with resource content is not empty that handles GET with an arbitrary payload"
            ],
            "state": "finished",
            "testcase_id": "TD_COAP_CORE_01",
            "testcase_ref": "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
            "verdict": "inconclusive"
        }

        """
        try:
            partial_verdict = tc_report.pop('partial_verdicts')
        except KeyError:
            partial_verdict = None
            logger.warning("No partial_verdicts for TC: %s" % tc_report['testcase_id'])

        table = list()
        fields = []

        step_message_fields = [
            ('verdict', 'Verdict'),
            ('description', 'Verdict info'),
            ('testcase_id', 'Test case ID'),
            ('objective', 'Test Purpose'),
            ('testcase_ref', 'Test case URL'),
            ('pre_conditions', 'Pre-conditions'),

        ]

        for i in step_message_fields:
            try:
                col1 = i[1]
                col2 = tc_report[i[0]]
                col2 = list_to_str(col2)  # flattens info
                table.append([col1, col2])
            except KeyError as e:
                logger.warning(e)

        fields.append({'type': 'p', 'value': tabulate(table, tablefmt="grid")})

        # 'warning' is yellow, 'highlighted' is green, and 'error' is red

        if 'verdict' in tc_report and 'pass' in tc_report['verdict']:
            display_color = 'highlighted'
        elif 'verdict' in tc_report and 'fail' in tc_report['verdict'].lower():
            display_color = 'error'
        elif 'verdict' in tc_report and 'error' in tc_report['verdict'].lower():
            display_color = 'error'
        elif 'verdict' in tc_report and 'none' in tc_report['verdict'].lower():
            display_color = 'error'
        else:
            display_color = 'warning'

        if partial_verdict:
            table_partial_verdicts = []
            frames = []
            table_partial_verdicts.append(('Step ID', 'Partial \nVerdict', 'Description'))
            for item in partial_verdict:
                try:
                    assert type(item) is list
                    cell_1 = item.pop(0)
                    cell_2 = item.pop(0)
                    cell_3 = list_to_str(item)
                    if 'Frame' in list_to_str(item):
                        frames.append(item)
                    table_partial_verdicts.append((cell_1, cell_2, cell_3))
                except Exception as e:
                    logger.error(e)
                    logger.error(traceback.format_exc())
                    break

            # add line
            fields.extend([{'type': 'p', 'value': '---\n'}])

            fields.extend([
                {'type': 'p', 'value': "Analysis Tool Checks:"},
                {'type': 'p', 'value': "%s" % tabulate(frames, tablefmt="grid")}
            ])

            # add line
            fields.extend([{'type': 'p', 'value': '---\n'}])

            fields.extend([
                {'type': 'p', 'value': "Step results:"},
                {'type': 'p', 'value': tabulate(table_partial_verdicts, tablefmt="grid", headers="firstrow")}
            ])

        return tc_report['testcase_id'], display_color, fields

    def _generate_ui_fields_for_pcap_download(self, testcase_id):

        pcap_download_fields = [{
            'type': 'p',
            'value': 'Testcase captures:\n'
        }]

        # FixMe! we know that filename includes the testcase_id! but this is ugly!
        for m in [i for i in self.session_history_messages if
                  isinstance(i, MsgSniffingGetCaptureReply) and testcase_id in i.filename]:

            if m.ok:
                logger.info("Found pcap in session history for %s" % testcase_id)
                pcap_download_fields.append({
                    "name": m.filename,
                    "type": "data",
                    "value": m.value,
                })
            else:
                logging.error('Sniffer responded with error to network traffic capture request: %s' % m)

            if not pcap_download_fields:  # syntax means if list is empty
                logging.warning('No capture found for testcase: %s' % testcase_id)

        return pcap_download_fields

    def _get_ui_testcase_verdict(self, message):
        verdict = message.to_dict()
        # fixme find a way of managing the "printable" fields, in a generic way
        verdict.pop('_api_version')  # we dont want to display the api version in UI

        # build report table
        tc_id, display_color, ui_fields = self._generate_ui_fields_for_testcase_report(verdict)

        # add line
        ui_fields.extend([{'type': 'p', 'value': '---\n'}])

        # add pcap downloads
        ui_fields += self._generate_ui_fields_for_pcap_download(message.testcase_id)

        return MsgUiDisplayMarkdownText(
            title="Verdict on TEST CASE: %s" % tc_id,
            level=display_color,
            fields=ui_fields,
        )

    def _get_ui_test_suite_results(self, message):
        """
        format of the message's body:
        {
        "tc_results": [
            {
                "testcase_id": "TD_COAP_CORE_01",
                "verdict": "pass",
                "description": "No interoperability error was detected,",
                "partial_verdicts":
                    [
                        ["TD_COAP_CORE_01_step_02", None, "CHECK postponed", ""],
                        ["TD_COAP_CORE_01_step_03", None, "CHECK postponed", ""],
                        ["TD_COAP_CORE_01_step_04", "pass",
                         "VERIFY step: User informed that the information was displayed "
                         "correclty on his/her IUT",
                         ""],
                        ["CHECK_1_post_mortem_analysis", "pass",
                         "<Frame   3: [bbbb::1 -> bbbb::2] CoAP [CON 43211] GET /test> Match: "
                         "CoAP(type=0, code=1)"],
                        ["CHECK_2_post_mortem_analysis", "pass",
                         "<Frame   4: [bbbb::2 -> bbbb::1] CoAP [ACK 43211] 2.05 Content > "
                         "Match: CoAP(code=69, mid=0xa8cb, tok=b'', pl=Not(b''))"],
                        [
                            "CHECK_3_post_mortem_analysis",
                            "pass",
                            "<Frame   4: [bbbb::2 -> bbbb::1] CoAP [ACK 43211] 2.05 Content > "
                            "Match: CoAP(opt=Opt(CoAPOptionContentFormat()))"]
                    ]
            },
            {
                "testcase_id": "TD_COAP_CORE_02",
                "verdict": "pass",
                "description": "No interoperability error was detected,",
                "partial_verdicts": [
                    ["TD_COAP_CORE_02_step_02", None, "CHECK postponed", ""],
                    ["TD_COAP_CORE_02_step_03", None, "CHECK postponed", ""],
                    ["TD_COAP_CORE_02_step_04", "pass",
                     "VERIFY step: User informed that the information was displayed correclty on his/her "
                     "IUT",
                     ""], ["CHECK_1_post_mortem_analysis", "pass",
                           "<Frame   3: [bbbb::1 -> bbbb::2] CoAP [CON 43213] DELETE /test> Match: CoAP(type=0, "
                           "code=4)"],
                    ["CHECK_2_post_mortem_analysis", "pass",
                     "<Frame   4: [bbbb::2 -> bbbb::1] CoAP [ACK 43213] 2.02 Deleted > Match: CoAP("
                     "code=66, mid=0xa8cd, tok=b'')"]]
            }
        ]
        }
        """

        fields = []
        fields_tail = []
        testcases = message.tc_results

        # add header
        summary_table = [["Testcase ID", "Verdict", "Description"]]
        display_color = 'highlighted'

        for tc_report in testcases:
            assert type(tc_report) is dict

            # add report basic info as a raw into the summary_table
            try:
                summary_table.append(
                    [
                        tc_report['testcase_id'],
                        tc_report['verdict'],
                        list_to_str(tc_report['description'])
                    ]
                )
            except KeyError:
                logger.warning("Couldnt parse: %s" % str(tc_report))
                summary_table.append([tc_report['testcase_id'], "None", "None"])

            # to add details we put it in the fields tail which will be displayed after the summary
            tc_id, tc_verdict_color, ui_fields = self._generate_ui_fields_for_testcase_report(tc_report)

            if tc_verdict_color is 'error':
                display_color = tc_verdict_color

            fields_tail = fields_tail + [{
                'type': 'p',
                'value': '---\n---\n%s:\n' % tc_id
            }]

            if type(ui_fields) is list:
                fields_tail = fields_tail + ui_fields
            else:
                logger.error("not a list: %s" % ui_fields)

        # add summary
        fields.append({'type': 'p', 'value': '%s' % (tabulate(summary_table, tablefmt="grid", headers="firstrow"))})

        fields.append({'type': 'p', 'value': 'see details on verdicts below'})

        # add long line as delimiter
        fields.append({'type': 'p', 'value': '-' * 70})

        # add tail (verdict details like checks etc..)
        fields = fields + fields_tail

        return MsgUiDisplayMarkdownText(
            title="Test suite report",
            level=display_color,
            fields=fields,
            tags=UI_TAG_REPORT,
        )

    def _get_ui_message_description_and_component(self, message):
        fields = [
            {
                'type': 'p',
                'value': '%s: %s' % (message.component, message.description)
            }
        ]
        return MsgUiDisplayMarkdownText(fields=fields)

    def _get_ui_testcase_skip(self, message):

        # default TC is current TC
        tc_id = message.testcase_id if message.testcase_id else 'current testcase'

        fields = [
            {
                'type': 'p',
                'value': '<%s> %s' % (tc_id, "has been chosen to be skipped by user")
            }
        ]
        return MsgUiDisplayMarkdownText(level='highlighted', fields=fields)

    def _get_ui_lossy_context(self, message):

        fields = [
            {
                'type': 'p',
                'value': 'Test configured to drop the following %s packet(s)' % message.number_of_packets_to_drop
            }
        ]
        return MsgUiDisplayMarkdownText(level='highlighted', fields=fields)

    def _get_ui_message_highlighted_description(self, message):
        fields = [
            {
                'type': 'p',
                'value': list_to_str(message.description)
            }
        ]

        return MsgUiDisplayMarkdownText(level='highlighted', tags={"testsuite": ""}, fields=fields)

    def _get_ui_message_steps(self, message):
        """
        STIMULI:

         description            Please execute step: TD_COAP_CORE_01_step_01
                                 Step description: ['Client is requested to send a GET request with', ['Type = 0(CON)', 'Code = 1(GET)']]
         target_address         coap://[bbbb::2]:5683
         _api_version           0.1.48
         node                   coap_client
         testcase_ref           http://doc.f-interop.eu/tests/TD_COAP_CORE_01
         state                  executing
         step_id                TD_COAP_CORE_01_step_01
         node_execution_mode    user_assisted
         testcase_id            TD_COAP_CORE_01
         step_type              stimuli
         node_address
         step_state             executing
         _type                  testcoordination.step.stimuli.execute
         step_info              Client is requested to send a GET request with
                                 Type = 0(CON)
                                 Code = 1(GET)

        or
        VERIFY:

         step_info              Client displays the received information
         description            Please execute step: TD_COAP_CORE_01_step_04
                                 Step description: ['Client displays the received information']
         _api_version           0.1.71
         testcase_id            TD_COAP_CORE_01
         step_id                TD_COAP_CORE_01_step_04
         node_execution_mode    user_assisted
         node_address
         node                   coap_client
         testcase_ref           http://doc.f-interop.eu/tests/TD_COAP_CORE_01
         _type                  testcoordination.step.verify.execute
         step_type              verify
         step_state             executing
         state                  executing
         response_type          bool

        """

        table = list()
        fields = []

        step_message_fields = [
            ('step_id', 'Step ID'),
            ('step_type', 'Step Type'),
            ('node', 'Node'),
            ('target_address', 'Address of target node'),
            ('testcase_id', 'Test case ID'),
            ('testcase_ref', 'Test case URL'),
            ('step_info', 'Description'),
        ]

        for i in step_message_fields:
            try:
                col1 = i[1]
                col2 = getattr(message, i[0])
                col2 = list_to_str(col2)  # flattens info
                table.append([col1, col2])
            except AttributeError as e:
                logger.warning(e)

        fields.append({'type': 'p', 'value': tabulate(table, tablefmt="grid")})

        return MsgUiDisplayMarkdownText(
            title="Please execute the %s STEP:" % message.step_type,
            level='info',
            fields=fields
        )

    def _get_ui_testing_tool_configured(self, message):
        """
        {
            "_api_version": "1.0.8",
            "content_type": "application/json",
            "description": "Testing tool CONFIGURED",
            "message_id": "9cc3ab2e-0844-4203-8106-3d66fd7d9d51",
            "session_id": "41c315b3-1ae9-4369-af9d-2e877a8bd734",
            "tc_list": [
                {
                    "notes": null,
                    "objective": "AE retrieves the CSEBase resource",
                    "pre_conditions": [
                        "CSEBase resource has been automatically created in CSE"
                    ],
                    "state": null,
                    "testcase_id": "TD_M2M_NH_01",
                    "testcase_ref": "http://doc.f-interop.eu/tests/TD_M2M_NH_01"
                },
                {
                    "notes": null,
                    "objective": "AE registers to its regisrar CSE via an AE Create Request",
                    "pre_conditions": [
                        "CSEBase resource has been created in CSE with name {CSEBaseName}",
                        "AE does not have an AE-ID, i.e it registers from scratch"
                    ],
                    "state": null,
                    "testcase_id": "TD_M2M_NH_06",
                    "testcase_ref": "http://doc.f-interop.eu/tests/TD_M2M_NH_06"
                },
                {
                    "notes": null,
                    "objective": "AE retrieves <AE> resource via an AE Retrieve Request",
                    "pre_conditions": [
                        "CSEBase resource has been created in registrar CSE with name {CSEBaseName}",
                        "AE has created a <AE> resource on registrar CSE with name {AE}"
                    ],
                    "state": null,
                    "testcase_id": "TD_M2M_NH_07",
                    "testcase_ref": "http://doc.f-interop.eu/tests/TD_M2M_NH_07"
                },
        {
        """

        fields_to_translate = ['testcase_id',
                               'objective',
                               'testcase_ref',
                               'pre_conditions',
                               'notes',
                               'state',
                               ]
        fields = []

        # 'state' gets special treatment
        fields_to_translate.remove('state')

        for f in message.tc_list:
            table = []
            if type(f) is dict:
                # 'state' gets special treatment
                state = f.pop('state') if 'state' in f else "Not yet executed."

                for field_name in fields_to_translate:
                    f_value = f[field_name]
                    table.append((field_name, f_value if type(f_value) is str else list_to_str(f_value)))

                # 'state' gets special treatment
                table.append(('state', state))

            fields.append({'type': 'p', 'value': '%s' % (tabulate(table, tablefmt="grid"))})
            fields.append({'type': 'p', 'value': '---\n'})

        return MsgUiDisplayMarkdownText(
            title=list_to_str(message.description),
            level='info',
            fields=fields,
            tags={"testsuite": ""}
        )

    def _get_ui_testcases_list(self, message):
        """
        {
            "_api_version": "1.0.8",
            "ok": true,
            "tc_list": [
                {
                    "state": null,
                    "testcase_id": "TD_M2M_NH_01",
                    "testcase_ref": "http://doc.f-interop.eu/tests/TD_M2M_NH_01"
                },
                {
                    "state": null,
                    "testcase_id": "TD_M2M_NH_06",
                    "testcase_ref": "http://doc.f-interop.eu/tests/TD_M2M_NH_06"
                },
                ...
                ]
        }

        """

        fields_to_translate = ['Test Case ID',
                               'Test Case URL',
                               'Test Case State',
                               ]
        fields = []
        table = []

        table.append(fields_to_translate)
        for f in message.tc_list:
            if type(f) is dict:
                table.append(
                    [
                        f['testcase_id'],
                        f['testcase_ref'],
                        f['state'] if f['state'] else "Not yet executed.",

                    ]
                )

        fields.append({'type': 'p', 'value': '%s' % (tabulate(table, tablefmt="grid", headers="firstrow"))})

        return MsgUiDisplayMarkdownText(
            title="Test cases list:",
            level='info',
            fields=fields,
            tags={"testsuite": ""}
        )

    def _get_ui_testcase_ready(self, message):
        table = list()
        fields = []

        step_message_fields = [
            ('testcase_id', 'Test Case ID'),
            ('testcase_ref', 'Test Case URL'),
            ('objective', 'Test Case Objective'),
            ('configuration_id', 'Configuration ID'),
            ('configuration_ref', 'Configuration URL'),
            ('pre_conditions', 'Test Case pre-conditions'),
            ('nodes', 'Nodes'),
            # ('nodes_description', 'Node Description'), # more complex structure, let's parse it separetly
        ]

        for i in step_message_fields:
            try:
                col1 = i[1]
                col2 = getattr(message, i[0])
                col2 = list_to_str(col2)  # flattens info
                table.append([col1, col2])
            except AttributeError as e:
                logger.warning(e)

        for desc in getattr(message, 'nodes_description'):
            table.append([desc['node'], list_to_str(desc['message'])])

        fields.append({'type': 'p', 'value': tabulate(table, tablefmt="grid")})

        return MsgUiDisplayMarkdownText(
            title='Next test case to be executed',
            level='info',
            fields=fields,
            tags={"testcase": message.testcase_id}
        )

    def _get_ui_testcase_configure(self, message):

        table = list()
        fields = []

        step_message_fields = [
            ('testcase_id', 'Test Case ID'),
            ('testcase_ref', 'Test Case URL'),
            ('node', 'Node'),
            ('description', 'Nodes Description')
        ]

        for i in step_message_fields:
            try:
                col1 = i[1]
                col2 = getattr(message, i[0])
                col2 = list_to_str(col2)  # flattens info
                table.append([col1, col2])
            except AttributeError as e:
                logger.warning(e)

        fields.append({'type': 'p', 'value': tabulate(table, tablefmt="grid")})

        return MsgUiDisplayMarkdownText(
            title="Please configure the IUT as indicated",
            level='info',
            fields=fields
        )

    def _get_ui_packet_dissected(self, message):
        """
            "_type": "dissection.autotriggered",
             "token": "0lzzb_Bx30u8Gu-xkt1DFE1GmB4",
            "frames": _frames_example,
            "testcase_id": "TBD",
            "testcase_ref": "TBD"

            format of frame list

            _frames_example = [
                {
                    "_type": "frame",
                    "id": 1,
                    "timestamp": 1464858393.547275,
                    "error": None,
                    "protocol_stack": [
                        {
                             "_type": "protocol",
                             "_protocol": "NullLoopback",
                            "AddressFamily": "2",
                            "ProtocolFamily": "0"
                        },
                        {
                            "_type": "protocol",
                            "_protocol": "IPv4",
                            "Version": "4",
                            "HeaderLength": "5",
                            "TypeOfService": "0x00",
                            "TotalLength": "41",
                            "Identification": "0x71ac",
                            "Reserved": "0",
                            "DontFragment": "0",
                            "MoreFragments": "0",
                            "FragmentOffset": "0",
                            "TimeToLive": "64",
                            "Protocol": "17",
                            "HeaderChecksum": "0x0000",
                            "SourceAddress": "127.0.0.1",
                            "DestinationAddress": "127.0.0.1",
                            "Options": "b''"
                        }
                ]
            },
        ]
        """

        fields = []
        frames_as_list_of_strings = message.frames_simple_text
        for frame_dict in message.frames:
            frame_header = []
            try:
                # display frame timestamp
                attribute_name = 'timestamp'
                attribute_value = datetime.datetime.fromtimestamp(int(frame_dict[attribute_name])).strftime(
                    '%Y-%m-%d %H:%M:%S')
                frame_header.append(["frame timestamp", attribute_value])

                # display frame errors
                attribute_name = 'error'
                attribute_value = frame_dict[attribute_name]
                if not attribute_value:
                    attribute_value = "None"
                frame_header.append(["frame error", attribute_value])

                # display dissections
                frame_header.append(['Dissection', '\n%s\n' % frames_as_list_of_strings.pop(0)])

            except KeyError as ae:
                logger.error("Some attribute was not found: %s" % str(frame_dict))
            try:
                fields.append({'type': 'p', 'value': '-' * 70})
                fields.append({'type': 'p', 'value': 'Frame:\n%s' % tabulate(frame_header, tablefmt="grid")})

            except KeyError as ae:
                logger.error("Some attribute was not found in protocol stack dict: %s" % str(frame_dict))

        return MsgUiDisplayMarkdownText(
            level='info',
            tags={"packets": self._current_tc if self._current_tc else ""},
            fields=fields,
        )

    def _get_ui_packet_raw(self, message):
        fields = []

        try:
            agent_name = message.routing_key.split('.')[1]
        except IndexError:
            agent_name = 'unknown_agent'

        # dont echo TT's agent messages
        if TESTING_TOOL_AGENT_NAME in agent_name:
            return

        if 'fromAgent' in message.routing_key:
            dir = '%s -> TESTING TOOL' % agent_name

        elif 'toAgent' in message.routing_key:
            dir = 'TESTING TOOL -> %s' % agent_name

        fields.append({'type': 'p', 'value': '%s: %s' % ('data packet', dir)})

        if message.timestamp:
            fields.append({'type': 'p', 'value': '%s:%s' % (
                'timestamp', datetime.datetime.fromtimestamp(int(message.timestamp)).strftime('%Y-%m-%d %H:%M:%S'))})

        fields.append({'type': 'p', 'value': '%s:%s' % ('interface', message.interface_name)})

        network_bytes_aligned = ''
        count = 0
        for int_value in message.data:
            network_bytes_aligned += format(int_value, '02x')
            if count == 7:
                network_bytes_aligned += ' \t'
                count += 1
            if count == 15:
                network_bytes_aligned += ' \n'
                count = 0
            else:
                network_bytes_aligned += ' '
                count += 1

        fields.append({'type': 'p', 'value': '\n%s' % (network_bytes_aligned)})

        return MsgUiDisplayMarkdownText(
            level='info',
            tags={"packets": self._current_tc if self._current_tc else ""},
            fields=fields,
        )

    def _get_ui_session_configuration(self, message):
        fields = []

        fields.append({'type': 'p', 'value': '%s: %s' % ('session_id', message.session_id)})
        fields.append({'type': 'p', 'value': '%s:%s' % ('users', message.users)})
        fields.append({'type': 'p', 'value': '%s:%s' % ('testing_tools', message.testing_tools)})

        try:
            testcases = message.configuration['testsuite.testcases']
            fields.append({'type': 'p', 'value': '%s:%s' % ('testcases', testcases)})
        except Exception as e:
            logger.warning('No testsuite.testcases in %s ' % repr(message))

        try:
            additional_session_resource = message.configuration['testsuite.additional_session_resource']
            fields.append(
                {'type': 'p', 'value': '%s:%s' % ('additional_session_resource', additional_session_resource)})
        except Exception as e:
            logger.warning("No testsuite.additional_session_resource in %s " % repr(message))

        return MsgUiDisplayMarkdownText(
            title='Current session configuration',
            level='info',
            tags={"testsuite": ""},
            fields=fields)

    def _get_ui_as_debug_messages(self, message):

        ret_msg = self._get_ui_message_as_table(message)
        ret_msg.tags = {"logs": ""}
        return ret_msg

    def _get_ui_agent_messages(self, message):
        fields = []

        if message:
            fields.append(
                {
                    'type': 'p',
                    'value': '%s TUN started, IPv6 interface %s::%s' % (
                        message.name, message.ipv6_prefix, message.ipv6_host)
                }
            )
        else:
            raise NotImplementedError()

        return MsgUiDisplayMarkdownText(
            tags=UI_TAG_SETUP,
            level='info',
            fields=fields
        )


class CoAPSessionMessageTranslator(GenericBidirectonalTranslator):
    IUT_ROLES = ['coap_client', 'coap_server']

    def __init__(self):
        super().__init__()

    def _bootstrap(self, amqp_connector):
        """
        see doc of overridden method

        only the following API calls should be used from bootstrap method:
            amqp_connector.synch_request(self, request, timeout)
            amqp_connector.publish_ui_display(self, message: Message, user_id=None, level=None)
        """

        # # # Get users connected to session # # #
        users = get_current_users_online(amqp_connector)

        if len(users) > 2:  # ignore if the rest of users (I assume they are "observer" users)
            users = users[:2]

        logger.info("Bootstrapping GUI adaptor for %s" % users)

        # # # Set Up the VPN between users' IUTs # # #

        # AGENT INFO
        agents_kickstart_help = vpn_setup
        agents_kickstart_help = agents_kickstart_help.replace('AgentNameHost1', self.IUT_ROLES[0])
        agents_kickstart_help = agents_kickstart_help.replace('AgentNameHost2', self.IUT_ROLES[1])

        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_INFO,
            fields=[{
                "type": "p",
                "value": agents_kickstart_help
            }, ]
        )
        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )

        for u in users:
            send_to_ui_confirmation_request(
                amqp_connector=amqp_connector,
                ui_msg="Confirm to continue",
                ui_tag=UI_TAG_AGENT_INFO,
                user=u,
            )

        # AGENT INSTALL
        agents_kickstart_help = agent_requirements + agent_install_help
        agents_kickstart_help = agents_kickstart_help.replace('AgentNameHost1', self.IUT_ROLES[0])
        agents_kickstart_help = agents_kickstart_help.replace('AgentNameHost2', self.IUT_ROLES[1])

        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_INSTALL,
            fields=[{
                "type": "p",
                "value": agents_kickstart_help
            }, ]
        )
        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )

        for u in users:
            send_to_ui_confirmation_request(
                amqp_connector=amqp_connector,
                ui_msg="Confirm installation finished",
                ui_tag=UI_TAG_AGENT_INSTALL,
                user=u,
            )

        # ENV VAR export
        disp = MsgUiDisplay(
                tags=UI_TAG_AGENT_CONNECT,
                fields=[{
                    "type": "p",
                    "value": env_vars_export
                }]
        )
        amqp_connector.publish_ui_display(
                message=disp,
                user_id='all'
        )

        for u in users:
            send_to_ui_confirmation_request(
                amqp_connector=amqp_connector,
                ui_msg="Confirm that variables have been exported",
                ui_tag=UI_TAG_AGENT_CONNECT,
                user=u,
            )

        # AGENT RUN
        agents_kickstart_help = help_agents_run_for_raw_ip_mode
        agents_kickstart_help = agents_kickstart_help.replace('AgentNameHost1', self.IUT_ROLES[0])
        agents_kickstart_help = agents_kickstart_help.replace('AgentNameHost2', self.IUT_ROLES[1])

        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_CONNECT,
            fields=[{
                "type": "p",
                "value": agents_kickstart_help
            }, ]
        )
        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )

        for u in users:
            send_to_ui_confirmation_request(
                amqp_connector=amqp_connector,
                ui_msg="Confirm that agent component is running",
                ui_tag=UI_TAG_AGENT_CONNECT,
                user=u,
            )

        # BOOTSTRAP INTERFACES

        send_start_test_suite_event()

        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_CONNECT,
            fields=[{
                "type": "p",
                "value": "bootstrapping agent(s) interface.."
            }, ]
        )

        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )

        #  TODO some prettier solution for this maybe?
        time.sleep(2)

        # TEST AGENT
        agents_kickstart_help = vpn_ping_tests
        agents_kickstart_help = agents_kickstart_help.replace('AgentNameHost1', self.IUT_ROLES[0])
        agents_kickstart_help = agents_kickstart_help.replace('AgentNameHost2', self.IUT_ROLES[1])

        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_TEST,
            fields=[{
                "type": "p",
                "value": agents_kickstart_help
            }, ]
        )
        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )

        for u in users:
            send_to_ui_confirmation_request(
                amqp_connector=amqp_connector,
                ui_msg="Confirm to continue",
                ui_tag=UI_TAG_AGENT_TEST,
                user=u,
            )

        return True

    # # # # # # # TT Messages # # # # # # # # # # # # # #

    def get_tt_message_testsuite_start(self, user_input, origin_tt_message=None):
        return MsgTestSuiteStart()

    def get_tt_message_testsuite_abort(self, user_input, origin_tt_message=None):
        return MsgTestSuiteAbort()

    def get_tt_message_testcase_start(self, user_input, origin_tt_message=None):
        return MsgTestCaseStart(testcase_id=self._current_tc)

    def get_tt_message_testcase_restart(self, user_input, origin_tt_message=None):
        return MsgTestCaseRestart()

    def get_tt_message_testcase_skip(self, user_input, origin_tt_message=None):
        return MsgTestCaseSkip(testcase_id=origin_tt_message.testcase_id)

    def get_tt_message_step_verify_executed(self, user_input, origin_tt_message=None):
        logger.info("processing: %s | %s" % (user_input, type(user_input)))

        if type(user_input) is str and user_input.lower() == 'true':
            user_input = True
        elif type(user_input) is str and user_input.lower() == 'false':
            user_input = False
        elif type(user_input) is bool:
            pass
        else:
            logger.error("Couldn't process user input %s" % user_input)
            return

        return MsgStepVerifyExecuted(
            response_type="bool",
            verify_response=user_input,
            # "node"= "coap_client",
            # "node_execution_mode": "user_assisted",
        )

    def get_tt_message_testcase_restart_last_executed(self, user_input, origin_tt_message=None):
        logger.info("processing: %s | %s" % (user_input, type(user_input)))

        if type(user_input) is not str:
            logger.error("Couldn't process user input %s" % user_input)
            return

        return MsgTestCaseSelect(
            testcase_id=user_input  # user_input = last executed testcase_id
        )

    def get_tt_message_step_stimuli_executed(self, user_input, origin_tt_message=None):
        # TODO fix harcoded values!
        return MsgStepStimuliExecuted(
            node="coap_client",
            node_execution_mode="user_assisted",
        )

    # # # # # # # UI Messages # # # # # # # # # # # # # #

    def _ui_request_testsuite_start(self, message_from_tt):
        fields = [
            {
                "name": "ts_start",
                "type": "button",
                "value": True
            },
        ]
        return MsgUiRequestConfirmationButton(
            title="Do you want to start the TEST SUITE?",
            fields=fields,
            tags={"testsuite": ""})

    def _ui_request_testcase_start(self, message_from_tt):
        message_ui_request = MsgUiRequestConfirmationButton(
            title="Do you want to start the TEST CASE <%s>?" % self._current_tc
        )
        message_ui_request.fields = [
            {
                "name": "tc_start",
                "type": "button",
                "value": True
            },
            {
                "name": "tc_skip",
                "type": "button",
                "value": True
            },
        ]
        return message_ui_request

    def _ui_request_step_stimuli_executed(self, message_from_tt):
        message_ui_request = MsgUiRequestConfirmationButton(
            # title="Do you confirm executing the STIMULI  <%s> ? " % self._current_step
        )
        message_ui_request.fields = [
            {
                "type": "p",
                "value": "Confirm executing %s (see description below)" % self._current_step
            },
            {
                "name": "stimuli_executed",
                "type": "button",
                "value": True
            },
        ]
        return message_ui_request

    def _ui_request_step_verification(self, message_from_tt):
        message_ui_request = MsgUiRequestConfirmationButton(
            # title="Please VERIFY the information regarding the STEP  <%s>" % self._current_step
        )
        message_ui_request.fields = [
            {
                "type": "p",
                "value": "Please verify %s (see description below)" % self._current_step
            },
            {
                "label": "OK",
                "name": "verify_executed",
                "type": "radio",
                "value": True
            },
            {
                "label": "Not OK",
                "name": "verify_executed",
                "type": "radio",
                "value": False
            },
        ]
        return message_ui_request

    def _ui_request_testcase_restart(self, message_from_tt):
        message_ui_request = MsgUiRequestConfirmationButton()
        message_ui_request.fields = [
            {
                "type": "p",
                "value": "Would you like to run again the test case?"
            },
            {
                "name": "restart_testcase",
                "type": "button",
                "value": self._current_tc
            },
        ]
        return message_ui_request


class CoMISessionMessageTranslator(CoAPSessionMessageTranslator):
    IUT_ROLES = ['comi_client', 'comi_server']

    def __init__(self):
        super().__init__()


class WoTSessionMessageTranslator(CoAPSessionMessageTranslator):
    # get nodes info, ip addresses etc from test configuration file
    # snippet on API use:
    """
    >>> a=testsuite.import_test_description_from_yaml(testsuite.TEST_DESCRIPTIONS_CONFIGS_DICT['wot'])[0]
    >>> a.
    a.configuration_diagram         a.get_default_addressing_table( a.get_target_node(              a.nodes                         a.to_dict(                      a.uri
    a.default_addressing            a.get_nodes_on_link(            a.id                            a.nodes_description             a.topology
    >>> a.get_default_addressing_table()
    [{'node': 'thing1', 'ipv6_prefix': 'bbbb', 'ipv6_host': 1}, {'node': 'thing2', 'ipv6_prefix': 'bbbb', 'ipv6_host': 2}, {'node': 'thing3', 'ipv6_prefix': 'bbbb', 'ipv6_host': 3}]
    """
    test_configs = testsuite.get_test_configurations_list_from_yaml(TD_WOT_CFG)
    assert len(test_configs) == 1
    test_config = test_configs.pop()
    node_addresses = test_config.get_default_addressing_table()
    IUT_ROLES = test_config.nodes

    PERIOD_FOR_STATS_UPDATES = 5  # in seconds

    def __init__(self):
        super().__init__()

        self.vpn_agents = OrderedDict()
        self.counters_packet_from_agents = OrderedDict()
        self.stats_update_datetime = datetime.datetime.now()

        # write default values for vpn agents table
        for node_dict in self.node_addresses:
            self.vpn_agents[node_dict['node']] = (node_dict['ipv6_prefix'], node_dict['ipv6_host'], None)

        # overrides handlers for certain UI messages
        self.specialized_visualization[MsgAgentTunStarted] = self._handle_new_agent_in_vpn
        self.specialized_visualization[MsgPacketSniffedRaw] = self._handle_new_packet_from_agent
        self.specialized_visualization[MsgPacketInjectRaw] = None

    def _bootstrap(self, amqp_connector):
        """
        see doc of overridden method

        only the following API calls should be used from bootstrap method:
            amqp_connector.synch_request(self, request, timeout)
            amqp_connector.publish_ui_display(self, message: Message, user_id=None, level=None)
        """

        # # # WELCOME MESSAGE # # #

        welcome_message = "### Welcome to Web of Things F-Interop playground!  \n" \
                          "##### This environment provides:\n" \
                          "    o IPv6 based VPN env where each implementation running a VPN client gets a private " \
                          "IPV6 address\n" \
                          "    o two virtualized WoT implementations (wot_thingweb and arenahub) are available on " \
                          "bbbb::101 and bbbb::102\n" \
                          "    o a virtualized CoAP server for testing, test GET coap://[bbbb::2]/test \n\n" \
                          "##### Notes: \n"\
                          "    o other users can join the same environment, click on the SHARE button " \
                          "(see blue button on the top-right) and share the link to do so\n" \
                          "    o VPN client (agent component) doesnt modify your OS default gateway\n"

        send_to_ui_confirmation_request(
            amqp_connector=amqp_connector,
            ui_msg=welcome_message,
            ui_tag=UI_TAG_SETUP,
        )

        # # # Set Up the VPN between users' IUTs # # #

        # AGENT INFO
        agents_kickstart_help = vpn_setup

        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_INFO,
            fields=[{
                "type": "p",
                "value": agents_kickstart_help
            }, ]
        )
        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )

        send_to_ui_confirmation_request(
            amqp_connector=amqp_connector,
            ui_tag=UI_TAG_AGENT_INFO,
        )

        # AGENT REQUIREMENTS
        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_REQUIREMENTS,
            fields=[{
                "type": "p",
                "value": agent_requirements
            }, ]
        )
        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )
        send_to_ui_confirmation_request(
            amqp_connector=amqp_connector,
            ui_tag=UI_TAG_AGENT_REQUIREMENTS,
        )

        # AGENT INSTALL
        agents_kickstart_help = agent_install_help

        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_INSTALL,
            fields=[{
                "type": "p",
                "value": agents_kickstart_help
            }, ]
        )
        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )
        send_to_ui_confirmation_request(
            amqp_connector=amqp_connector,
            ui_tag=UI_TAG_AGENT_INSTALL,
            ui_msg="Confirm installation finished",
        )

        # RUN agent and connect to VPN
        send_vpn_join_help_to_user(self.vpn_agents,user='all')

        # RUN agent and connect to VPN
        send_to_ui_confirmation_request(
            amqp_connector=amqp_connector,
            ui_tag=UI_TAG_AGENT_CONNECT,
            ui_msg="Confirm that agent has been started as described below"
        )

        # TEST AGENT
        agents_kickstart_help = vpn_ping_tests
        agents_kickstart_help = agents_kickstart_help.replace('AgentNameHost1', self.IUT_ROLES[0])
        agents_kickstart_help = agents_kickstart_help.replace('AgentNameHost2', self.IUT_ROLES[1])

        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_TEST,
            fields=[{
                "type": "p",
                "value": agents_kickstart_help
            }, ]
        )
        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )

        send_to_ui_confirmation_request(
            amqp_connector=amqp_connector,
            ui_tag=UI_TAG_AGENT_TEST,
        )

        # BOOTSTRAP INTERFACES
        bootstrap_all_tun_interfaces(amqp_connector,self.vpn_agents)

        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_CONNECT,
            fields=[{
                "type": "p",
                "value": "bootstrapping agent(s) interface.."
            }, ]
        )

        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )  # TODO some prettier solution for this maybe?

        return True

    def _send_vpn_table_to_gui(self, amqp_connector):

        table = _get_vpn_table_representation(self.vpn_agents)
        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_CONNECT,
            fields=[{
                "type": "p",
                "value": "Agents in VPN:\n{}".format(tabulate(table, tablefmt="grid", headers="firstrow"))
            }, ]
        )
        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )

    def _handle_new_agent_in_vpn(self, message):

        fields = []

        if message.name and message.ipv6_prefix and message.ipv6_host:
            self.vpn_agents[message.name] = (message.ipv6_prefix, message.ipv6_host, datetime.datetime.now())
            table = _get_vpn_table_representation(self.vpn_agents)
            fields.append(
                {
                    'type': 'p',
                    'value': '%s TUN started, IPv6 interface %s::%s' % (message.name, message.ipv6_prefix, message.ipv6_host)
                }
            )

            fields.append(
                {
                    'type': 'p',
                    "value": "Agents in VPN:\n{}".format(tabulate(table, tablefmt="grid", headers="firstrow"))
                }
            )

        return MsgUiDisplayMarkdownText(
            tags=UI_TAG_VPN_STATUS,
            fields=fields
        )

    def _handle_new_packet_from_agent(self, message):
        """
        +1 to packet count
        displays stats in GUI (if certain conditions are met)
        """

        agent_name = message.routing_key.split('.')[1]

        try:
            self.counters_packet_from_agents[agent_name] += 1
        except KeyError:
            self.counters_packet_from_agents[agent_name] = 1

        if (datetime.datetime.now() - self.stats_update_datetime).seconds > self.PERIOD_FOR_STATS_UPDATES:

            ascii_table = tabulate(
                [("source", "number of packets sent")] + list(self.counters_packet_from_agents.items()),
                tablefmt="grid",
                headers="firstrow"
            )

            self.stats_update_datetime = datetime.datetime.now()

            return MsgUiDisplay(
                tags=UI_TAG_VPN_STATUS,
                fields=[{"type": "p", "value": "IPv6 packets stats:\n%s" % ascii_table},]
            )
        return

    def callback_on_new_users_in_the_session(self, amqp_connector, new_user_list):

        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_TEST,
            fields=[{
                "type": "p",
                "value": "New user on session detected: {}".format(new_user_list)
            }, ]
        )
        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )

        #self._bootstrap(amqp_connector)
        send_vpn_join_help_to_user(self.vpn_agents, user='all')


class OneM2MSessionMessageTranslator(CoAPSessionMessageTranslator):
    IUT_ROLES = ['adn', 'cse']

    def __init__(self):
        super().__init__()


class LwM2MSessionMessageTranslator(CoAPSessionMessageTranslator):
    IUT_ROLES = ['lwm2m_client', 'lwm2m_server']

    def __init__(self):
        super().__init__()


class SixLoWPANSessionMessageTranslator(CoAPSessionMessageTranslator):
    IUT_ROLES = ['eut1', 'eut2']

    def __init__(self):
        super().__init__()

    def _bootstrap(self, amqp_connector):
        """
        see doc of overridden method

        only the following API calls should be used from bootstrap method:
            amqp_connector.synch_request(self, request, timeout)
            amqp_connector.publish_ui_display(self, message: Message, user_id=None, level=None)
        """

        # # # Set Up the VPN between users' IUTs # # #
        # 1. user needs to config AGENT and PROBE

        # in 6lowpan we redirect the user towards the official doc
        agents_kickstart_help = """Please read documentation for 6LoWPAN (802.15.4) testing suite:
        
testbed setup: http://doc.f-interop.eu/interop/6lowpan_test_suite
        
test descriptions: http://doc.f-interop.eu/testsuites/6lowpan
"""

        req = MsgUiRequestConfirmationButton(
            tags=UI_TAG_AGENT_CONNECT,
            fields=[
                {
                    "type": "p",
                    "value": agents_kickstart_help
                },
                {
                    "name": "continue",
                    "type": "button",
                    "value": True
                },
            ]
        )

        try:
            resp = amqp_connector.synch_request(
                request=req,
                timeout=900,
            )
        except Exception:  # fixme import and hanlde AmqpSynchCallTimeoutError only
            pass

        disp = MsgUiDisplay(
            tags=UI_TAG_AGENT_CONNECT,
            fields=[
                {
                    "type": "p",
                    "value": env_vars_export
                }]
        )
        amqp_connector.publish_ui_display(
            message=disp,
            user_id='all'
        )
        req = MsgUiRequestConfirmationButton(
            title="Confirm that agent and probe are up and running",
            tags=UI_TAG_AGENT_CONNECT,
            fields=[{
                "name": "confirm",
                "type": "button",
                "value": True
            }, ]
        )

        try:
            resp = amqp_connector.synch_request(
                request=req,
                timeout=600,
            )
        except Exception:  # fixme import and hanlde AmqpSynchCallTimeoutError only
            pass

        send_start_test_suite_event()

        return True

        # 3. TODO trigger agents configuration
        # 4. TODO automate ping test from tt
        # 5. TODO ask user to ping other user's endpoint


class DummySessionMessageTranslator(GenericBidirectonalTranslator):
    IUT_ROLES = ['example_role_1', 'example_role_2']

    def _bootstrap(self, amqp_connector):
        import inspect

        snippets = [self.snippet_display_markdown,
                    self.snippet_request_button,
                    self.snippet_request_radio,
                    self.snippet_request_checkbox,
                    self.snippet_request_select,
                    self.snippet_request_file]

        self.basic_display("This will demonstrate the basic calls for using the UI by using the "
                           "[utils](https://gitlab.f-interop.eu/f-interop-contributors/utils) library",
                           tags={"tutorial": ""})

        for example in snippets:
            logger.info('demoing %s' % example.__name__)
            time.sleep(10)
            markdown_text = ""
            markdown_text += ("\n-----------\n")
            markdown_text += ("\n```\n")
            markdown_text += (inspect.getsource(example))
            markdown_text += ("\n```\n")
            markdown_text += ("\n-----------\n")
            self.basic_display(markdown_text, tags={"tutorial": ""})
            markdown_text2 = ("the example will executed in 10 seconds, "
                              "you can navigate through the tags by clicking on the timeline on the top left..")
            self.basic_display(markdown_text2, tags={"tutorial": ""})

            time.sleep(10)
            example()

    def snippet_display_markdown(self):
        """
        This snippet shows how to display a message to all users (ui.user.all.display), using the
        [utils](https://gitlab.f-interop.eu/f-interop-contributors/utils) library
        """
        # this imports are absolute, for your case these will probably change
        from messages import MsgUiDisplayMarkdownText
        from event_bus_utils import amqp_request, publish_message
        import pika

        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
        AMQP_URL = str(os.environ['AMQP_URL'])
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        message = MsgUiDisplayMarkdownText(
            title="Hello world Title!",
            level='highlighted',
            tags={"snippet": "display_markdown"},
            fields=[
                {
                    'type': 'p',
                    'value': "## Hello world message using MD :)"
                }
            ]
        )
        publish_message(connection, message)

    def snippet_request_button(self):
        """
        This snippet shows how to request a confirmation to a users (any) (ui.user.any.display), using the
        [utils](https://gitlab.f-interop.eu/f-interop-contributors/utils)
        library.

        (!) This is using a synchronous approach with a timeout. Dont expect to build your whole UI doing
        syncrhonous calls tho :P

        """
        # this imports are absolute, for your case these will probably change
        from messages import MsgUiRequestConfirmationButton
        from event_bus_utils import amqp_request, publish_message, AmqpSynchCallTimeoutError
        import pika

        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
        AMQP_URL = str(os.environ['AMQP_URL'])
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        ui_request = MsgUiRequestConfirmationButton(
            title="Hello world Title!",
            level='highlighted',
            tags={"snippet": "button"},
            fields=[
                {
                    "name": "confirmation_button",
                    "type": "button",
                    "value": True
                },
            ]
        )

        try:
            ui_reply = amqp_request(connection,
                                    ui_request,
                                    'dummy_component',
                                    retries=5,
                                    time_between_retries=1)
        except AmqpSynchCallTimeoutError:
            self.basic_display("The message request: \n`%s`" % repr(ui_request),
                               tags={"snippet": "button"})

            self.basic_display("The message reply was never received :/ did you click on the confirmation button?",
                               tags={"snippet": "button"})
            return

        self.basic_display("The message request: \n`%s`" % repr(ui_request),
                           tags={"snippet": "button"})
        self.basic_display("The message reply: \n`%s`" % repr(ui_reply),
                           tags={"snippet": "button"})

    def snippet_request_radio(self):
        """
        This snippet shows how to request a confirmation to a users (any) (ui.user.any.display), using the
        [utils](https://gitlab.f-interop.eu/f-interop-contributors/utils)
        library.

        (!) This is using a synchronous approach with a timeout. Dont expect to build your whole UI doing
        syncrhonous calls tho :P

        """
        # this imports are absolute, for your case these will probably change
        from messages import MsgUiRequestConfirmationButton
        from event_bus_utils import amqp_request, publish_message, AmqpSynchCallTimeoutError
        import pika

        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
        AMQP_URL = str(os.environ['AMQP_URL'])
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        ui_request = MsgUiRequestQuestionRadio(
            title="This is a question",
            tags={"snippet": "radio"}
        )

        try:
            ui_reply = amqp_request(connection,
                                    ui_request,
                                    'dummy_component',
                                    retries=5,
                                    time_between_retries=1)
        except AmqpSynchCallTimeoutError:
            self.basic_display("The message request: \n`%s`" % repr(ui_request),
                               tags={"snippet": "radio"})
            self.basic_display("The message reply was never received :/",
                               tags={"snippet": "radio"})
            return

        self.basic_display("The message request: \n`%s`" % repr(ui_request),
                           tags={"snippet": "radio"})
        self.basic_display("The message reply: \n`%s`" % repr(ui_reply),
                           tags={"snippet": "radio"})

    def snippet_request_checkbox(self):
        """
        This snippet shows how to request a confirmation to a users (any) (ui.user.any.display), using the
        [utils](https://gitlab.f-interop.eu/f-interop-contributors/utils)
        library.

        (!) This is using a synchronous approach with a timeout. Dont expect to build your whole UI doing
        syncrhonous calls tho :P

        """
        # this imports are absolute, for your case these will probably change
        from messages import MsgUiRequestConfirmationButton
        from event_bus_utils import amqp_request, publish_message, AmqpSynchCallTimeoutError
        import pika

        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
        AMQP_URL = str(os.environ['AMQP_URL'])
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        ui_request = MsgUiRequestQuestionCheckbox(
            title="It's a matter of choice",
            tags={"snippet": "checkbox"}
        )

        try:
            ui_reply = amqp_request(connection,ui_request,'dummy_component',retries=5,time_between_retries=1)
        except AmqpSynchCallTimeoutError:
            self.basic_display("The message request: \n`%s`" % repr(ui_request),
                               tags={"snippet": "checkbox"})
            self.basic_display("The message reply was never received :/",
                               tags={"snippet": "checkbox"})
            return

        self.basic_display("The message request: \n`%s`" % repr(ui_request),
                           tags={"snippet": "checkbox"})
        self.basic_display("The message reply: \n`%s`" % repr(ui_reply),
                           tags={"snippet": "checkbox"})

    def snippet_request_select(self):
        """
        This snippet shows how to request a confirmation to a users (any) (ui.user.any.display), using the
        [utils](https://gitlab.f-interop.eu/f-interop-contributors/utils)
        library.

        (!) This is using a synchronous approach with a timeout. Dont expect to build your whole UI doing
        syncrhonous calls tho :P

        """
        # this imports are absolute, for your case these will probably change
        from messages import MsgUiRequestConfirmationButton
        from event_bus_utils import amqp_request, publish_message, AmqpSynchCallTimeoutError
        import pika

        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
        AMQP_URL = str(os.environ['AMQP_URL'])
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        ui_request = MsgUiRequestQuestionSelect(
            title="It's a matter of choice",
            tags={"snippet": "select"}
        )

        try:
            ui_reply = amqp_request(connection,
                                    ui_request,
                                    'dummy_component',
                                    retries=5,
                                    time_between_retries=1)
        except AmqpSynchCallTimeoutError:
            self.basic_display("The message request: \n`%s`" % repr(ui_request),
                               tags={"snippet": "select"})
            self.basic_display("The message reply was never received :/",
                               tags={"snippet": "select"})
            return

        self.basic_display("The message request: \n`%s`" % repr(ui_request),
                           tags={"snippet": "select"})
        self.basic_display("The message reply: \n`%s`" % repr(ui_reply),
                           tags={"snippet": "select"})

    def snippet_request_file(self):
        """
        This snippet shows how to request a confirmation to a users (any) (ui.user.any.display), using the
        [utils](https://gitlab.f-interop.eu/f-interop-contributors/utils)
        library.

        (!) This is using a synchronous approach with a timeout. Dont expect to build your whole UI doing
        syncrhonous calls tho :P

        """
        # this imports are absolute, for your case these will probably change
        from messages import MsgUiRequestConfirmationButton
        from event_bus_utils import amqp_request, publish_message, AmqpSynchCallTimeoutError
        import pika

        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
        AMQP_URL = str(os.environ['AMQP_URL'])
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        ui_request = MsgUiRequestUploadFile(
            title="Give me your file!",
            tags={"snippet": "file"}
        )

        try:
            ui_reply = amqp_request(connection,
                                    ui_request,
                                    'dummy_component',
                                    retries=5,
                                    time_between_retries=1)
        except AmqpSynchCallTimeoutError:
            self.basic_display("The message request: \n`%s`" % repr(ui_request),
                               tags={"snippet": "file_upload"})
            self.basic_display("The message reply was never received :/",
                               tags={"snippet": "file_upload"})
            return

        self.basic_display("The message request: \n`%s`" % repr(ui_request),
                           tags={"snippet": "file_upload"})
        self.basic_display("The message reply: \n`%s`" % repr(ui_reply),
                           tags={"snippet": "file_upload"})

    def basic_display(self, text: str, tags={}):
        from messages import MsgUiDisplayMarkdownText
        from event_bus_utils import publish_message
        import pika

        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
        AMQP_URL = str(os.environ['AMQP_URL'])
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        message = MsgUiDisplayMarkdownText(
            tags=tags,
            fields=[
                {
                    'type': 'p',
                    'value': "%s" % text
                }
            ]
        )
        publish_message(connection, message)

# __all__ = [
#     GenericBidirectonalTranslator,
#     CoAPSessionMessageTranslator,
#     OneM2MSessionMessageTranslator,
#     LwM2MSessionMessageTranslator,
#     SixLoWPANSessionMessageTranslator,
#     CoMISessionMessageTranslator,
# ]
