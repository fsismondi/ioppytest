import logging
import time

from ioppytest.ui_adaptor.ui_tasks import get_session_configuration_from_ui
from ioppytest.ui_adaptor import (AmqpSynchCallTimeoutError,
                                  MsgSessionConfiguration,
                                  MsgAgentTunStart,
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


def wait_for_testing_tool_ready(amqp_publisher, max_retries=5):
    retries_left = max_retries
    while retries_left != 0:
        try:
            amqp_publisher.synch_request(request=MsgTestSuiteGetTestCases(),
                                         timeout=2)
            return
        except AmqpSynchCallTimeoutError:
            logging.debug("testing tool not up yet, retries left: %s" % retries_left)

        retries_left -= 1
        time.sleep(1)

    if retries_left == 0:
        raise SessionError("Couldn't detect Testing Tool up")


def bootstrap_all_tun_interfaces(amqp_publisher, vpn_table):
        """
        Starts tun interface in user's agents.
        Forces all agents to send current config they have already started their tun interfaces.
        This is best effort approach, no exception is raised if the bootstrapping fails
        """
        # vpn table is creates as  { agent_name : (ipv6_prefix, ipv6_host, last_connection) , ...}
        for agent_name, agent_info in vpn_table.items():
            logging.info("starting/updating info for %s"%agent_name)
            ipv6_network_prefix = str(agent_info[0])
            ipv6_host = str(agent_info[1])
            #assigned_ip = ":{}".format(ipv6_host)

            msg = MsgAgentTunStart(
                name=agent_name,
                ipv6_prefix=ipv6_network_prefix,
                ipv6_host=ipv6_host,
                ipv6_no_forwarding=False,
            )

            msg.routing_key = msg.routing_key.replace('*', agent_name)

            amqp_publisher.publish_message(msg)