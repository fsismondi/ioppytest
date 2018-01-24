import logging
import time

from ioppytest.finterop_ui_adaptor.ui_tasks import get_session_configuration_from_ui
from ioppytest.finterop_ui_adaptor import (AmqpSynchCallTimeoutError,
                                           MsgSessionConfiguration,
                                           SessionError,
                                           MsgTestSuiteGetTestCases, )


def configure_testing_tool(amqp_publisher):
    s_config = get_session_configuration_from_ui(amqp_publisher)
    msg = MsgSessionConfiguration(session_id=s_config["id"],
                                  configuration=s_config["configuration"],
                                  testing_tools=s_config["testSuite"],
                                  users=s_config["users"], )
    amqp_publisher.publish_message(msg)


def wait_for_testing_tool_ready(amqp_publisher):
    retries_left = 20
    while retries_left >= 0:
        time.sleep(0.5)
        try:
            amqp_publisher.synch_request(request=MsgTestSuiteGetTestCases(),
                                         timeout=5)
            return
        except AmqpSynchCallTimeoutError:
            logging.debug("testing tool not up yet, retries left: %s" % retries_left)

        retries_left -= 1

    if retries_left < 0:
        raise SessionError("Couldn't detect Testing Tool up")
