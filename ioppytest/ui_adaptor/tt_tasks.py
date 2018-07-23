import logging
import time

from ioppytest.ui_adaptor.ui_tasks import get_session_configuration_from_ui
from ioppytest.ui_adaptor import (AmqpSynchCallTimeoutError,
                                  MsgSessionConfiguration,
                                  SessionError,
                                  MsgTestSuiteGetTestCases, )


def send_default_testing_tool_configuration(amqp_publisher):
    """
    Send empty configuration message to TT
    """

    msg = MsgSessionConfiguration(
        session_id="666",
        configuration={},
        testing_tools="",
        users=[],
    )
    amqp_publisher.publish_message(msg)


def configure_testing_tool(amqp_publisher):
    s_config = get_session_configuration_from_ui(amqp_publisher)
    msg = MsgSessionConfiguration(session_id=s_config["id"],
                                  configuration=s_config["configuration"],
                                  testing_tools=s_config["testSuite"],
                                  users=s_config["users"], )
    amqp_publisher.publish_message(msg)


def wait_for_testing_tool_ready(amqp_publisher):
    retries_left = 3
    while retries_left != 0:
        try:
            amqp_publisher.synch_request(request=MsgTestSuiteGetTestCases(),
                                         timeout=2)
            return
        except AmqpSynchCallTimeoutError:
            logging.debug("testing tool not up yet, retries left: %s" % retries_left)

        retries_left -= 1
        time.sleep(0.5)

    if retries_left == 0:
        raise SessionError("Couldn't detect Testing Tool up")
