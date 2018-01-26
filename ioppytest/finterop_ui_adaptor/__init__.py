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
]

WAITING_TIME_FOR_SECOND_USER = 500  # in seconds
SESSION_SETUP_TAG = {'session_setup': ''}


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
