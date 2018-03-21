import os

from ioppytest.utils.messages import *
from ioppytest.utils.event_bus_utils import AmqpSynchCallTimeoutError


STDOUT_MAX_TEXT_LENGTH_PER_LINE = 120
STDOUT_MAX_TEXT_LENGTH = STDOUT_MAX_TEXT_LENGTH_PER_LINE * 30  # 30 lines of max line length
STDOUT_MAX_STRING_LENGTH_KEY_COLUMN = 30
STDOUT_MAX_STRING_LENGTH_VALUE_COLUMN = STDOUT_MAX_TEXT_LENGTH_PER_LINE - STDOUT_MAX_STRING_LENGTH_KEY_COLUMN

COMPONENT_ID = 'ui_adaptor'

MESSAGES_NOT_TO_BE_ECHOED = [
    MsgTestCaseStarted,
    MsgSessionLog,
    MsgTestingToolComponentReady,
    MsgUiRequestSessionConfiguration,
    MsgUiSessionConfigurationReply,
    MsgSessionConfiguration,
    MsgAgentConfigured,
    MsgAgentTunStart,
    MsgAgentTunStarted,
    MsgTestingToolConfigured,
    MsgTestSuiteGetTestCases,
    MsgDissectionAutoDissect
]

WAITING_TIME_FOR_SECOND_USER = 900  # in seconds

UI_TAG_SETUP = {"session_setup": ""}
UI_TAG_BOOTSTRAPPING = {"session_boostrap": ""}
UI_TAG_REPORT = {"testsuite_report": ""}


TESTING_TOOL_TOPIC_SUBSCRIPTIONS = [
    'testingtool.#',
    'testsuite.#',
    'session.#',
    #'log.#'
    'fromAgent.#',  # do not subscribe to toAgent else we will have duplication in GUI
]


class UiResponseError(Exception):
    pass


class SessionError(Exception):
    pass
