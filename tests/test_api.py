# -*- coding: utf-8 -*-
# !/usr/bin/env python3

from coap_testing_tool.utils.event_bus_messages import *
from tests.database_pcap_base64 import *
from urllib.parse import urlparse

import unittest
import pika
import sys
import time
import os
import threading
import datetime

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
services_backlog = []

# a very simple & rustic lock for handling the access to the backlog
# TODO create a backlog class and put the lock in there
lock = threading.Lock()

"""
PRE-CONDITIONS:
- Export AMQP_URL in the running environment
- Have CoAP testing tool and listening to the bus
"""

# for a typical user input, for a user (coap client) vs automated-iut ( coap server) session type:
user_sequence = [
    MsgTestSuiteGetStatus(),
    MsgTestSuiteStart(),
    MsgTestSuiteGetStatus(),
    MsgTestCaseSkip(testcase_id='TD_COAP_CORE_02_v01'),
    MsgTestSuiteGetStatus(),
    MsgTestCaseSkip(testcase_id='TD_COAP_CORE_03_v01'),
    MsgTestSuiteGetStatus(),
    MsgTestCaseSkip(testcase_id='TD_COAP_CORE_04_v01'),
    MsgTestSuiteGetStatus(),
    MsgTestCaseStart(),
    MsgTestSuiteGetStatus(),
    MsgStimuliExecuted(),
    MsgTestSuiteGetStatus(),
    MsgVerifyResponse(),
    MsgTestSuiteGetStatus(),
    MsgVerifyResponse(
            verify_response=False,
            description='User indicates that IUT didnt behave as expected '),
    MsgTestSuiteGetStatus(),
    # at this point we should see a TC verdict
    MsgTestCaseRestart(),
    MsgTestSuiteGetStatus(),
    MsgTestSuiteAbort(),
    MsgTestSuiteGetStatus(),
]

service_api_calls = [
    # TAT calls
    MsgTestSuiteGetStatus(),
    MsgTestSuiteGetTestCases(),
    MsgInteropTestCaseAnalyze(
            testcase_id="TD_COAP_CORE_01",
            testcase_ref="http://f-interop.paris.inria.fr/tests/TD_COAP_CORE_01_v01",
            file_enc="pcap_base64",
            filename="TD_COAP_CORE_01.pcap",
            value=PCAP_TC_COAP_01_base64,
    ),

    # Sniffer calls (order matters!)
    MsgSniffingStart(
            capture_id='TD_COAP_CORE_01',
            filter_if='tun0',
            filter_proto='udp port 5683'
    ),
    MsgSniffingStop(),
    MsgSniffingGetCapture(tescase_id='TD_COAP_CORE_01'),
    MsgSniffingGetCaptureLast(),

    # Dissector calls
    MsgDissectionDissectCapture(),
    MsgDissectionDissectCapture(
            file_enc="pcap_base64",
            filename="TD_COAP_CORE_01.pcap",
            protocol_selection='coap',
            value=PCAP_TC_COAP_01_base64,
    ),
    # complete dissection of pcap
    MsgDissectionDissectCapture(
            file_enc="pcap_base64",
            filename="TD_COAP_CORE_01.pcap",
            value=PCAP_TC_COAP_01_base64,
    ),
    # complete dissection of pcap with extra TCP traffic
    MsgDissectionDissectCapture(
            file_enc="pcap_base64",
            filename="TD_COAP_CORE_01.pcap",
            value=PCAP_TC_COAP_01_mingled_with_tcp_traffic_base64,
    ),
    # same as dis4 but filtering coap messages
    MsgDissectionDissectCapture(
            file_enc="pcap_base64",
            filename="TD_COAP_CORE_01.pcap",
            protocol_selection='coap',
            value=PCAP_TC_COAP_01_mingled_with_tcp_traffic_base64,
    ),
    # pcap sniffed using AMQP based packet sniffer
    MsgDissectionDissectCapture(
            file_enc="pcap_base64",
            filename="TD_COAP_CORE_01.pcap",
            value=PCAP_COAP_GET_OVER_TUN_INTERFACE_base64,
    )
]


class ApiTests(unittest.TestCase):
    def setUp(self):

        global stop_generator_signal
        stop_generator_signal = False

        import_env_vars()

        self.conn = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.conn.channel()

        # CONTROL EVENTS QUEUE
        control_queue_name = 'control_queue@%s' % COMPONENT_ID

        # lets' first clean up the queue
        self.channel.queue_delete(queue=control_queue_name)

        self.channel.queue_declare(queue=control_queue_name, auto_delete=True)
        self.channel.queue_bind(exchange=AMQP_EXCHANGE, queue=control_queue_name, routing_key='control.#')
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(validate_message, queue=control_queue_name)

        # SERVICES & REPLIES QUEUE
        services_queue_name = 'services_queue@%s' % COMPONENT_ID

        # lets' first clean up the queue
        self.channel.queue_delete(queue=services_queue_name)

        self.channel.queue_declare(queue=services_queue_name, auto_delete=True)
        self.channel.queue_bind(exchange=AMQP_EXCHANGE, queue=services_queue_name, routing_key='#.service')
        self.channel.queue_bind(exchange=AMQP_EXCHANGE, queue=services_queue_name, routing_key='#.service.reply')
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(validate_request_replies, queue=services_queue_name)

        # ERRORS LOGS AND OTHER ERROR EVENTS QUEUE
        errors_queue_name = 'bus_errors_queue@%s' % COMPONENT_ID

        # lets' first clean up the queue
        self.channel.queue_delete(queue=errors_queue_name)

        self.channel.queue_declare(queue=errors_queue_name, auto_delete=True)
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=errors_queue_name,
                                routing_key='log.error.*')
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=errors_queue_name,
                                routing_key='session.error')

        # for getting the terminate signal
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=errors_queue_name,
                                routing_key=MsgSessionTerminate.routing_key)
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(check_for_bus_error, queue=errors_queue_name)

    def tearDown(self):
        self.conn.close()

    def test_user_emulation(self):

        # prepare the message generator
        messages = []  # list of messages to send
        messages += user_sequence
        messages.append(MsgSessionTerminate())  # message that triggers stop_generator_signal

        thread_msg_gen = MessageGenerator(AMQP_URL, AMQP_EXCHANGE, messages)
        logger.debug("Starting Message Generator thread ")
        thread_msg_gen.start()

        try:
            self.channel.start_consuming()
        except NonCompliantMessageFormatError as e:
            thread_msg_gen.stop()
            assert False, str(e)

        except Exception as e:
            thread_msg_gen.stop()
            assert False, str(e)

    def test_testing_tool_internal_services(self):
        services_queue_name = 'bus_errors_queue@%s' % COMPONENT_ID

        channel = self.conn.channel()
        # lets' first clean up the queue
        channel.queue_delete(queue=services_queue_name)

        channel.queue_declare(queue=services_queue_name, auto_delete=True)
        channel.queue_bind(exchange=AMQP_EXCHANGE,
                           queue=services_queue_name,
                           routing_key='*.error.*')

        channel.queue_bind(exchange=AMQP_EXCHANGE,
                           queue=services_queue_name,
                           routing_key='session.error')

        # for getting the terminate signal
        channel.queue_bind(exchange=AMQP_EXCHANGE,
                           queue=services_queue_name,
                           routing_key=MsgSessionTerminate.routing_key)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(check_for_bus_error, queue=services_queue_name)

        # prepare the message generator
        messages = []  # list of messages to send
        messages += service_api_calls
        messages.append(MsgSessionTerminate())  # message that triggers stop_generator_signal

        thread_msg_gen = MessageGenerator(AMQP_URL, AMQP_EXCHANGE, messages)
        logger.debug("Starting Message Generator thread ")
        thread_msg_gen.start()

        try:
            channel.start_consuming()
            if len(services_backlog)>0:
                assert False, 'A least one of the services request was not answered. backlog: %s' % services_backlog
        except Exception as e:
            thread_msg_gen.stop()
            assert False, str(e)

    def test_non_existent_types_in_message_library_dont_generate_validation_errors(self):
        messages = []  # list of messages to send
        m = MsgInteropTestCaseAnalyze()
        m._type = 'some.non.existent.message.type'
        messages += [m]
        messages += service_api_calls
        messages.append(MsgSessionTerminate())  # message that triggers stop_generator_signal

        thread_msg_gen = MessageGenerator(AMQP_URL, AMQP_EXCHANGE, messages)
        logger.debug("Starting Message Generator thread ")
        thread_msg_gen.start()

        try:
            self.channel.start_consuming()
        except NonCompliantMessageFormatError as e:
            thread_msg_gen.stop()
            assert False, str(e)


# # # # # # AUXILIARY METHODS # # # # # # #


def import_env_vars():
    global AMQP_EXCHANGE
    global AMQP_URL

    try:
        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
    except KeyError as e:
        AMQP_EXCHANGE = "default"

    try:
        AMQP_URL = str(os.environ['AMQP_URL'])
        p = urlparse(AMQP_URL)
        AMQP_USER = p.username
        AMQP_SERVER = p.hostname
        logger.info(
                "Env variables imported for AMQP connection, User: {0} @ Server: {1} ".format(AMQP_USER, AMQP_SERVER)
        )
    except KeyError as e:
        logger.error('Cannot retrieve environment variables for AMQP connection. Loading defaults..')
        # load default values
        AMQP_URL = "amqp://{0}:{1}@{2}/{3}".format("guest", "guest", "localhost", "/")

    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

    # in case its not declared
    connection.channel().exchange_declare(exchange=AMQP_EXCHANGE,
                                          type='topic',
                                          durable=True,
                                          )
    connection.close()


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
    logger.info('Checking for error messages in the bus')

    try:
        m = Message.from_json(body)
        if isinstance(m, MsgSessionTerminate):
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

    ]
    r_key = method.routing_key
    logger.info('Auditing: %s' % r_key)

    for c in list_of_audited_components:
        if c in r_key:
            logger.error('audited component %s pushed an error into the bus' % c)
            raise Exception('audited component %s pushed an error into the bus' % c)

def validate_request_replies(ch, method, props, body):
    global lock
    lock.acquire()
    global services_backlog


    body_dict = json.loads(body.decode('utf-8'), object_pairs_hook=OrderedDict)
    ch.basic_ack(delivery_tag=method.delivery_tag)
    logging.info("[%s] got message: %s" %(sys._getframe().f_code.co_name, body_dict['_type']) )
    if '.service.reply' in method.routing_key:
        if props.correlation_id in services_backlog:
            services_backlog.remove(props.correlation_id)
        else:
            assert False,'got a reply but didnt see the request passing!'

    elif '.service' in method.routing_key:
        services_backlog.append(props.correlation_id)
    else:
        assert False, 'error! we shouldnt be here!'

    lock.release()
    logging.info("[%s] current backlog: %s" % (sys._getframe().f_code.co_name, services_backlog))



def validate_message(ch, method, props, body):
    global message_count
    # obj hook so json.loads respects the order of the fields sent -just for visualization purposeses-
    req_body_dict = json.loads(body.decode('utf-8'), object_pairs_hook=OrderedDict)
    ch.basic_ack(delivery_tag=method.delivery_tag)
    message_count += 1

    print('\n* * * * * * MESSAGE SNIFFED by INSPECTOR (%s) * * * * * * *' % message_count)
    print("TIME: %s" % datetime.datetime.time(datetime.datetime.now()))
    print("ROUTING_KEY: %s" % method.routing_key)
    print("MESSAGE ID: %s" % props.message_id)
    if hasattr(props,'correlation_id'):
        print("CORRELATION ID: %s" % props.correlation_id)
    print('EVENT %s' % (req_body_dict['_type']))
    print('* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * \n')

    if props.content_type != "application/json":
        print('* * * * * * API VALIDATION WARNING * * * * * * * ')
        print("props.content_type : " + str(props.content_type))
        print("application/json was expected")
        print('* * * * * * * * * * * * * * * * * * * * * * * * *  \n')
        raise Exception

    if '_type' not in req_body_dict.keys():
        print('* * * * * * API VALIDATION WARNING * * * * * * * ')
        print("no < _type > field found")
        print('* * * * * * * * * * * * * * * * * * * * * * * * *  \n')
        raise Exception

    # lets check messages against the messaging library
    list_of_messages_to_check = list(message_types_dict.keys())
    if req_body_dict['_type'] in list_of_messages_to_check:
        m = Message.from_json(body)
        try:
            if isinstance(m, MsgSessionTerminate):
                ch.stop_consuming()
                stop_generator()
            else:
                logger.debug(repr(m))
        except NonCompliantMessageFormatError as e:
            print('* * * * * * API VALIDATION WARNING * * * * * * * ')
            print("AMQP MESSAGE LIBRARY COULD PROCESS JSON MESSAGE")
            print('* * * * * * * * * * * * * * * * * * * * * * * * *  \n')
            raise NonCompliantMessageFormatError("AMQP MESSAGE LIBRARY COULD PROCESS JSON MESSAGE")


class MessageGenerator(threading.Thread):
    keepOnRunning = True

    def __init__(self, amqp_url, amqp_exchange, messages_list):
        threading.Thread.__init__(self)
        self.messages = messages_list
        self.connection = pika.BlockingConnection(pika.URLParameters(amqp_url))
        self.channel = self.connection.channel()
        logger.info("AMQP connection established")

    def run(self):
        global MESSAGES_WAIT_INTERVAL

        logger.info(
                "let's start 'blindly' generating the messages which take part on a coap session (for a coap client)"
        )

        try:
            while self.keepOnRunning:
                time.sleep(MESSAGES_WAIT_INTERVAL)
                m = self.messages.pop(0)
                publish_message(self.channel, m)
                logger.info("Publishing in the bus: %s" % repr(m))
        except IndexError:
            # list finished, lets wait so all messages are sent and processed
            time.sleep(5)
            pass
        except pika.exceptions.ChannelClosed:
            pass

    def stop(self):
        self.keepOnRunning = False
        self.connection.close()
