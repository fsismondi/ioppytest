import os
import json
import logging
from collections.__init__ import OrderedDict

from tabulate import tabulate
from event_bus_utils import AmqpListener, publish_message
from messages import (MsgUiRequestSessionConfiguration,
                      MsgTestingToolTerminate,
                      MsgTestSuiteReport,
                      MsgUiSessionConfigurationReply
                      )

from ioppytest.ui_adaptor.message_translators import list_to_str

logger = logging.getLogger(__name__)

TESTSUITE_NAME = os.environ.get('TESTNAME', 'noname')
TESTSUITE_REPORT_DELIM = os.environ.get('DELIM', '===TESTRESULT===')
default_configuration = {
    "testsuite.testcases": [
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_02",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_03",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_04",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_05",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_06",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_07",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_08",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_09",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_10"
    ]
}


def testsuite_results_to_ascii_table(testcases_results: list):
    """
    :param tc_resutls: list of test cases results
    :return: string-based (ascii chars) table of all results
    """

    # add header
    summary_table = [["Testcase ID", "Verdict", "Description"]]

    for tc_report in testcases_results:
        assert type(tc_report) is dict

        # add report basic info as a raw into the summary_table
        try:
            summary_table.append(
                [
                    tc_report['testcase_id'],
                    tc_report['verdict'],
                    list_to_str(tc_report['description'])
                ]
            )
        except KeyError:
            logger.warning("Couldnt parse: %s" % str(tc_report))
            summary_table.append([tc_report['testcase_id'], "None", "None"])

    return tabulate(summary_table, tablefmt="grid", headers="firstrow")


class UIStub(AmqpListener):
    def __init__(self, amqp_url, amqp_exchange):
        AmqpListener.__init__(self, amqp_url, amqp_exchange,
                              callback=self.process_message,
                              topics=[
                                  MsgUiRequestSessionConfiguration.routing_key,
                                  MsgTestingToolTerminate.routing_key,
                                  MsgTestSuiteReport.routing_key
                              ],
                              use_message_typing=True)

    def process_message(self, message):
        if isinstance(message, MsgUiRequestSessionConfiguration):
            resp = {
                "configuration": default_configuration,
                "id": '666',
                "testSuite": "someTestingToolName",
                "users": ['pablo', 'bengoechea'],
            }
            m = MsgUiSessionConfigurationReply(
                message,
                **resp
            )
            publish_message(self.connection, m)
        elif isinstance(message, MsgTestSuiteReport):

            verdict_content = OrderedDict()
            verdict_content['testname'] = TESTSUITE_NAME
            verdict_content.update(message.to_odict())

            logger.info("%s %s %s", TESTSUITE_REPORT_DELIM, json.dumps(verdict_content, indent=4),
                        TESTSUITE_REPORT_DELIM)
            logger.info("%s: \n%s ", "Test Suite Table Report", testsuite_results_to_ascii_table(message.tc_results))


        elif isinstance(message, MsgTestingToolTerminate):
            logger.info("Received termination message. Stopping UIStub")
            self.stop()
        else:
            logger.warning(
                'reply_to_ui_configuration_request_stub got not expected message type %s' % str(type(message)))
