import threading
import logging
import pika
import time
import sys

from ioppytest import AMQP_URL, AMQP_EXCHANGE
from ioppytest.utils.messages import *
from ioppytest.utils.event_bus_utils import publish_message

logging.basicConfig(level=logging.INFO,
                    format='[%(levelname)s] (%(threadName)-10s): %(message)s', )

default_configuration = {
    "testsuite.testcases": [
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_02",
        "http://doc.f-interop.eu/tests/TD_COAP_CORE_03"
    ]
}

MAX_LINE_LENGTH = 120


# # # # # # AUXILIARY TEST METHODS # # # # # # #

def log_all_received_messages(event_types_sniffed_on_bus_list: list):
    logging.info("Events sniffed in bus: %s" % len(event_types_sniffed_on_bus_list))
    i = 0
    for ev in event_types_sniffed_on_bus_list:
        i += 1
        try:

            log_line = "\n\tevent count: %s" % i
            log_line += "\n\tmsg_id: %s" % ev.message_id
            log_line += "\n\tmsg repr: %s" % repr(ev)[:MAX_LINE_LENGTH]
            if isinstance(ev, MsgSessionLog):
                log_line += "\n\tmessage from %s: %s" % (ev.component,ev.message)

            logging.info(log_line)

        except AttributeError as e:
            logging.warning("No message id in message: %s" % repr(ev))


def reply_to_ui_configuration_request_stub(message: Message):
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
        connect_and_publish_message(m)
    else:
        logging.warning('reply_to_ui_configuration_request_stub got not expected message type %s' % str(type(message)))


def connect_and_publish_message(message: Message):
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    publish_message(
        connection,
        message
    )


def publish_terminate_signal_on_report_received(message: Message):
    if isinstance(message, MsgTestSuiteReport):
        logging.info('Got final report %s' % repr(message))
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        publish_message(
            connection,
            MsgTestingToolTerminate(description="Received report, functional test finished..")
        )


def check_if_message_is_an_error_message(message: Message, fail_on_reply_nok=True):
    logging.info('[%s]: %s' % (sys._getframe().f_code.co_name, type(message)))

    # it's ok if UI adaptor generates errors, as we there is not UI responding to request in the bus when testing
    if isinstance(message, MsgSessionLog) and 'ui_adaptor' in message.component:
        return

    assert 'error' not in message.routing_key, \
        'Got an error on message, \n\tid: %s ,\n\tmsg repr: %s' % (message.message_id, repr(message))

    assert not isinstance(message, MsgErrorReply), \
        'Got an ErrorReply on message, \n\tid: %s ,\n\tmsg repr: %s' % (message.message_id, repr(message))

    if fail_on_reply_nok:
        assert not (isinstance(message, MsgReply) and not message.ok), \
            'Got a reply with a NOK reponse %s' % repr(message)


def check_api_version(message: Message):
    try:
        assert message._api_version, 'Message didnt enclude API version metadata %s' % repr(message)
    except:
        logging.warning('Message didnt enclude API version metadata %s' % repr(message))
        return

    assert message._api_version.startswith("1"), "Using very old version of API spec %s" % repr(message)


class MessageGenerator(threading.Thread):
    """
        blindly' publishes messages in list until it's empty
    """
    keepOnRunning = True

    def __init__(self, amqp_url, amqp_exchange, messages_list, wait_time_between_pubs=2):
        threading.Thread.__init__(self)
        self.messages = messages_list
        self.wait_time_between_pubs = wait_time_between_pubs
        self.connection = pika.BlockingConnection(pika.URLParameters(amqp_url))
        self.channel = self.connection.channel()
        logging.info("[%s] AMQP connection established" % (self.__class__.__name__))

    def run(self):
        logging.info("[%s] lets start 'blindly' generating the messages which take part on a coap session "
                     "(for a coap client)" % (self.__class__.__name__))
        try:
            while self.keepOnRunning:
                time.sleep(self.wait_time_between_pubs)
                m = self.messages.pop(0)
                publish_message(self.connection, m)
                logging.info("[%s] Publishing in the bus: %s" % (self.__class__.__name__, repr(m)))

        except IndexError:
            # list finished, lets wait so all messages are sent and processed
            time.sleep(5)
            pass

        except pika.exceptions.ChannelClosed:
            pass

        finally:
            logging.info("[%s] shutting down.. " % (self.__class__.__name__))
            self.connection.close()

    def stop(self):
        self.keepOnRunning = False
