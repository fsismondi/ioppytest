import os

from ioppytest.utils.messages import MsgTestCaseStarted

STDOUT_MAX_STRING_LENGTH = 70

MESSAGES_NOT_TO_BE_ECHOED = [
    MsgTestCaseStarted
]

COMPONENT_ID = 'ui_adaptor'

try:
    AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
except KeyError:
    AMQP_EXCHANGE = "amq.topic"

try:
    AMQP_URL = str(os.environ['AMQP_URL'])
    print('Env vars for AMQP connection succesfully imported')
except KeyError:
    AMQP_URL = "amqp://guest:guest@localhost/"

