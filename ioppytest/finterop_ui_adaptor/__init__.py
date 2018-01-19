import os

from ioppytest.utils.messages import *

STDOUT_MAX_STRING_LENGTH = 70

COMPONENT_ID = 'ui_adaptor'

MESSAGES_NOT_TO_BE_ECHOED = [
    MsgTestCaseStarted,
    MsgSessionLog
]

TESTING_TOOL_TOPIC_SUBSCRIPTIONS = [
    'testingtool.#',
    'testsuite.#',
    'session.#',
    #'log.#'
    'fromAgent.#',  # do not subscribe to toAgent else we will have duplication in GUI
]

UI_REPLY_TOPICS = [
    'ui.user.1.reply',
    'ui.user.2.reply',
    'ui.user.all.reply',
]


class UiResponseError(Exception):
    pass
