# -*- coding: utf-8 -*-
# !/usr/bin/env python3

from coap_testing_tool.utils.event_bus_messages import *
from automated_IUTs.automation import UserMock
from urllib.parse import urlparse
import logging

import unittest
import pika
import sys
import time
import os
import threading

COMPONENT_ID = 'fake_session'
MESSAGES_WAIT_INTERVAL = 1  # in seconds
AMQP_EXCHANGE = ''
AMQP_URL = ''
message_count = 0
stop_generator_signal = False

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

logging.getLogger('pika').setLevel(logging.INFO)

# queue which tracks all non answered services requests
events_sniffed_on_bus = {}  # the dict allows us to index last received messages of each type
event_types_sniffed_on_bus = []  # the list allows us to monitor the order of events

"""
PRE-CONDITIONS:
- Export AMQP_URL in the running environment
- Have CoAP testing tool running & listening to the bus
- Have an automated-iut coap client and an automated-iut coap server running & listening to the bus
"""


class SessionMockTests(unittest.TestCase):
    def setUp(self):
        global stop_generator_signal
        stop_generator_signal = False
        import_env_vars()
        self.conn = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.conn.channel()

    def tearDown(self):
        self.conn.close()

    def test_testcase_TD_COAP_CORE_01_pass(self):
        global event_types_sniffed_on_bus
        global events_sniffed_on_bus
        THREAD_JOIN_TIMEOUT = 300

        tc_list = ['TD_COAP_CORE_01_v01']  # the rest of the testcases are going to be skipped
        u = UserMock(tc_list)
        e = EventListener(AMQP_URL)

        try:

            u.start()
            e.start()
            publish_message(self.channel,
                            MsgInteropSessionConfiguration()  # from TC1 to TC3
                            )
            u.join(THREAD_JOIN_TIMEOUT)  # waits THREAD_JOIN_TIMEOUT for the session to terminate

        except Exception as e:
            assert False, "Exception encountered %s" % e

        finally:

            publish_message(self.channel,
                            MsgTestingToolTerminate())  # this should terminate all processes listening in the bus

            if u.is_alive():
                u.join()

            if e.is_alive():
                e.join()

            report_type = MsgTestSuiteReport()._type

            logging.error("EVENTS: %s" % event_types_sniffed_on_bus)
            logging.info(events_sniffed_on_bus[report_type])

            assert report_type in event_types_sniffed_on_bus, "Testing tool didnt emit any report"
            assert report_type in events_sniffed_on_bus, "Testing tool didnt emit any report"


# # # # # # AUXILIARY METHODS # # # # # # #

def import_env_vars():
    global AMQP_EXCHANGE
    global AMQP_URL

    try:
        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
    except KeyError:
        AMQP_EXCHANGE = "amq.topic"

    try:
        AMQP_URL = str(os.environ['AMQP_URL'])
        p = urlparse(AMQP_URL)
        AMQP_USER = p.username
        AMQP_SERVER = p.hostname
        logger.info(
            "Env variables imported for AMQP connection, User: {0} @ Server: {1} ".format(AMQP_USER, AMQP_SERVER)
        )
    except KeyError:
        logger.error('Cannot retrieve environment variables for AMQP connection. Loading defaults..')
        # load default values
        AMQP_URL = "amqp://{0}:{1}@{2}/{3}".format("guest", "guest", "localhost", "/")


def publish_message(channel, message):
    properties = pika.BasicProperties(**message.get_properties())

    channel.basic_publish(
        exchange=AMQP_EXCHANGE,
        routing_key=message.routing_key,
        properties=properties,
        body=message.to_json(),
    )


def stop_generator():
    global stop_generator_signal
    logger.debug("The test is finished!")
    stop_generator_signal = True


def check_for_bus_error(ch, method, props, body):
    logger.info('[%s] Checking if is error, message %s' % (sys._getframe().f_code.co_name, props.message_id))

    try:
        msg = Message.from_json(body)
        if isinstance(msg, MsgTestingToolTerminate):
            ch.stop_consuming()
            return
    except:
        pass

    list_of_audited_components = [
        'tat',
        'test_coordinator',
        'packer_router',
        'sniffer',
        'dissector'
        'session',
        # TODO add agent_TT messages
    ]
    r_key = method.routing_key
    logger.info('[%s] Auditing: %s' % (sys._getframe().f_code.co_name, r_key))

    for c in list_of_audited_components:
        if c in r_key:
            err = 'audited component %s pushed an error into the bus. messsage: %s' % (c, body)
            logger.error(err)
            raise Exception(err)


class MessageGenerator(threading.Thread):
    keepOnRunning = True

    def __init__(self, amqp_url, amqp_exchange, messages_list):
        threading.Thread.__init__(self)
        self.messages = messages_list
        self.connection = pika.BlockingConnection(pika.URLParameters(amqp_url))
        self.channel = self.connection.channel()
        logger.info("[%s] AMQP connection established" % (self.__class__.__name__))

    def run(self):
        global MESSAGES_WAIT_INTERVAL
        logger.info("[%s] lets start 'blindly' generating the messages which take part on a coap session "
                    "(for a coap client)" % (self.__class__.__name__))
        try:
            while self.keepOnRunning:
                time.sleep(MESSAGES_WAIT_INTERVAL)
                m = self.messages.pop(0)
                publish_message(self.channel, m)
                logger.info("[%s] Publishing in the bus: %s" % (self.__class__.__name__, repr(m)))
        except IndexError:
            # list finished, lets wait so all messages are sent and processed
            time.sleep(5)
            pass
        except pika.exceptions.ChannelClosed:
            pass

    def stop(self):
        self.keepOnRunning = False
        self.connection.close()


class EventListener(threading.Thread):
    COMPONENT_ID = __name__

    def __init__(self, amqp_url):
        global event_types_sniffed_on_bus
        global events_sniffed_on_bus

        threading.Thread.__init__(self)
        self.connection = pika.BlockingConnection(pika.URLParameters(amqp_url))
        self.channel = self.connection.channel()
        logger.info("[%s] AMQP connection established" % (self.__class__.__name__))

        all_messages_queue = 'all_messages_queue@%s' % self.COMPONENT_ID

        # lets' first clean up the queue
        self.channel.queue_delete(queue=all_messages_queue)
        self.channel.queue_declare(queue=all_messages_queue, auto_delete=True)
        self.channel.queue_bind(exchange=AMQP_EXCHANGE, queue=all_messages_queue, routing_key='#')

        # for catching the terminate signal
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=all_messages_queue,
                                routing_key=MsgTestingToolTerminate.routing_key)

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.update_events_seen_on_bus_list, queue=all_messages_queue)

    def update_events_seen_on_bus_list(self, ch, method, props, body):
        global event_types_sniffed_on_bus
        global events_sniffed_on_bus

        ch.basic_ack(delivery_tag=method.delivery_tag)

        try:

            m = Message.from_json(body)
            if m is None:
                logger.error("[%s] Couldnt get message yet did not raise error: %s" %
                             (self.__class__.__name__, str(body)))
                return
            logger.info("[%s] Message received type: %s" % (self.__class__.__name__, m._type))
            if isinstance(m, MsgTestingToolTerminate):
                self.stop()
            else:
                events_sniffed_on_bus[m._type] = m
                event_types_sniffed_on_bus.append(m._type)

        except NonCompliantMessageFormatError as e:
            logger.warning("[%s] Non compliant message found: %s" % (self.__class__.__name__, e))

    def run(self):
        self.channel.start_consuming()

    def stop(self):
        self.channel.stop_consuming()
        self.connection.close()
