from ioppytest.finterop_ui_adaptor import *
from ioppytest.finterop_ui_adaptor.ui_tasks import get_session_configuration_from_ui


def configure_testing_tool(amqp_publisher):
    s_config = get_session_configuration_from_ui(amqp_publisher)
    assert s_config, "Got session config None from UI"

    keys_to_validate = {"id", "configuration", "testSuite", "users"}
    assert keys_to_validate.issubset(s_config), "Expected %s, Got  %s" % (keys_to_validate, s_config.keys())

    msg = MsgSessionConfiguration(
        session_id=s_config["id"],
        configuration=s_config["configuration"],
        testing_tools=s_config["testSuite"],
        users=s_config["users"],
    )
    logging.info("about to leave")
    amqp_publisher.publish_message(msg)


def wait_for_testing_tool_ready(amqp_publisher):
    max_retries = 20
    while max_retries >= 0:
        time.sleep(0.5)
        try:
            amqp_publisher.synch_request(MsgTestSuiteGetTestCases())
            logging.debug("testing tool is replying messages!")
            return
        except:
            logging.debug("testing tool not up yet")

        max_retries -= 1

    if max_retries < 0:
        raise SessionError("Couldnt detect Testing Tool up")
