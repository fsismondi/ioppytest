import os

from ioppytest.utils.messages import *
from ioppytest.utils.event_bus_utils import AmqpSynchCallTimeoutError

STDOUT_MAX_STRING_LENGTH = 70

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
    MsgTestingToolConfigured,
    MsgTestSuiteGetTestCases
]

WAITING_TIME_FOR_SECOND_USER = 900  # in seconds

UI_TAG_SETUP = {"session_setup": ""}
UI_TAG_BOOTSTRAPPING = {"session_boostrap": ""}


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
