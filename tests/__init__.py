import threading
import logging
import pika
import time
import sys

from ioppytest import AMQP_URL, AMQP_EXCHANGE
from ioppytest.utils.messages import *
from ioppytest.utils.event_bus_utils import publish_message

logging.basicConfig(level=logging.DEBUG,
                    format='[%(levelname)s] (%(threadName)-10s): %(message)s', )


# # # # # # AUXILIARY TEST METHODS # # # # # # #

def publish_terminate_signal_on_report_received(message: Message):
    if isinstance(message, MsgTestSuiteReport):
        logging.info('Got final report %s' % repr(message))
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        publish_message(
            connection,
            MsgTestingToolTerminate(description="Received report, functional test finished..")
        )


def check_if_message_is_an_error_message(message: Message):
    logging.info('[%s]: %s' % (sys._getframe().f_code.co_name, type(message)))
    assert 'error' not in message.routing_key, 'Got an error %s' % repr(message)
    assert not isinstance(message, MsgErrorReply), 'Got an error reply %s' % repr(message)
    assert not (isinstance(message, MsgReply) and message.ok == False), 'Got a reply with a NOK reponse %s' % repr(
        message)


def check_api_version(message: Message):
    try:
        assert message._api_version, 'Message didnt enclude API version metadata %s' % repr(message)
    except:
        logging.warning('Message didnt enclude API version metadata %s' % repr(message))
        return

    assert message._api_version.startswith("1"), "Running incompatible version of API %s" % repr(message)


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
