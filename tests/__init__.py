import threading
import logging
import pika
import time

from ioppytest.utils.event_bus_utils import publish_message

logging.basicConfig(level=logging.DEBUG,
                    format='[%(levelname)s] (%(threadName)-10s): %(message)s', )


class MessageGenerator(threading.Thread):
    """
        blindly' publishes messages in list until it's empty
    """
    keepOnRunning = True

    def __init__(self, amqp_url, amqp_exchange, messages_list, wait_time_between_pubs):
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
