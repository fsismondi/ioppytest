import json
import logging
import os
from collections.__init__ import OrderedDict

from ioppytest.utils.event_bus_utils import AmqpListener, publish_message
from ioppytest.utils.messages import MsgUiRequestSessionConfiguration, MsgTestingToolTerminate, MsgTestSuiteReport, \
    MsgUiSessionConfigurationReply

logger = logging.getLogger(__name__)

TESTSUITE_NAME = os.environ.get('TESTNAME', 'noname')
TESTSUITE_REPORT_DELIM = os.environ.get('DELIM', '===TESTRESULT===')
default_configuration = {
    "testsuite.testcases": [
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_02",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_03"
    ]
}
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

            logger.info("%s %s %s", TESTSUITE_REPORT_DELIM, json.dumps(verdict_content, indent=4) ,TESTSUITE_REPORT_DELIM)


        elif isinstance(message, MsgTestingToolTerminate):
            logger.info("Received termination message. Stopping UIStub")
            self.stop()
        else:
            logger.warning(
                'reply_to_ui_configuration_request_stub got not expected message type %s' % str(type(message)))