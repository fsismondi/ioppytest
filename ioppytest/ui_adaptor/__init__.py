import os

from messages import *
from event_bus_utils import AmqpSynchCallTimeoutError


STDOUT_MAX_TEXT_LENGTH_PER_LINE = 120
STDOUT_MAX_TEXT_LENGTH = STDOUT_MAX_TEXT_LENGTH_PER_LINE * 100  # ~100 lines, each line of a max line length
STDOUT_MAX_STRING_LENGTH_KEY_COLUMN = 30
STDOUT_MAX_STRING_LENGTH_VALUE_COLUMN = STDOUT_MAX_TEXT_LENGTH_PER_LINE - STDOUT_MAX_STRING_LENGTH_KEY_COLUMN

COMPONENT_ID = 'ui_adaptor'

MESSAGES_NOT_TO_BE_ECHOED = [
    MsgSniffingGetCaptureReply,
    MsgSniffingGetCapture,
    MsgTestSuiteStart,
    MsgTestCaseStarted,
    MsgSessionLog,
    MsgTestingToolComponentReady,
    MsgUiRequestSessionConfiguration,
    MsgUiSessionConfigurationReply,
    MsgAgentTunStart,
    MsgTestingToolConfigured,
    MsgTestSuiteGetTestCases,
]

WAITING_TIME_FOR_SECOND_USER = 900  # in seconds

# GUI api says that <tags> are dicts
UI_TAG_SETUP = {"session_setup": ""}
UI_TAG_AGENT_REQUIREMENTS = {"agents_requirements": ""}
UI_TAG_AGENT_INSTALL = {"agents_install": ""}
UI_TAG_AGENT_CONNECT = {"agents_connect": ""}
UI_TAG_AGENT_INFO = {"agents_info": ""}
UI_TAG_AGENT_TEST = {"agents_test": ""}
UI_TAG_REPORT = {"testsuite_report": ""}
UI_TAG_VPN_STATUS = {"vpn_status": ""}


TESTING_TOOL_TOPIC_SUBSCRIPTIONS = [
    'sniffing.getcapture.*',
    'testingtool.#',
    'testsuite.#',
    'session.#',
    #'log.#',
    'fromAgent.#',
    'toAgent.#',
    MsgRoutingStartLossyLink.routing_key
]

class UiResponseError(Exception):
    pass


class SessionError(Exception):
    pass
