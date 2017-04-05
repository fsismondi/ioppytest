# -*- coding: utf-8 -*-
# !/usr/bin/env python3

from coap_testing_tool.utils.event_bus_messages import *
from tests.database_pcap_base64 import *
from urllib.parse import urlparse

import pika
import sys
import time
import os
import threading
import datetime


COMPONENT_ID = 'fake_session'
MESSAGES_WAIT_INTERVAL = 1 # in seconds
message_count = 0
shutdown = False


def publish_message(channel, message):
    properties = pika.BasicProperties(**message.get_properties())

    channel.basic_publish(
            exchange=AMQP_EXCHANGE,
            routing_key=message.routing_key,
            properties=properties,
            body=message.to_json(),
    )

def _shutdown():
    global shutdown
    logging.info("The test is finished!")
    shutdown = True


def on_request(ch, method, props, body):
        global message_count
        # obj hook so json.loads respects the order of the fields sent -just for visualization purposeses-
        req_body_dict = json.loads(body.decode('utf-8'),object_pairs_hook=OrderedDict)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        message_count += 1


        print('\n* * * * * * MESSAGE SNIFFED by INSPECTOR (%s) * * * * * * *'%message_count)
        print("TIME: %s"%datetime.datetime.time(datetime.datetime.now()))
        print("ROUTING_KEY: %s" % method.routing_key)
        print('EVENT %s' %(req_body_dict['_type']))
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


        # lets check messages agains the messaging library
        list_of_messages_to_check = list(message_types_dict.keys())
        if req_body_dict['_type'] in list_of_messages_to_check:
            m = Message.from_json(body)
            try:
                if isinstance(m,MsgTestSuiteAbort):
                    ch.stop_consuming()
                    _shutdown()
                else:
                    print(repr(m))
            except NonCompliantMessageFormatError as e:
                print('* * * * * * API VALIDATION WARNING * * * * * * * ')
                print("AMQP MESSAGE LIBRARY COULD PROCESS JSON MESSAGE")
                print('* * * * * * * * * * * * * * * * * * * * * * * * *  \n')
                raise NonCompliantMessageFormatError("AMQP MESSAGE LIBRARY COULD PROCESS JSON MESSAGE")


class MessageGenerator(threading.Thread):

    def __init__(self, amqp_url, amqp_exchange):
        threading.Thread.__init__(self)
        self.connection = pika.BlockingConnection(pika.URLParameters(amqp_url))
        self.channel = connection.channel()
        logging.info("AMQP connection established")

    def run(self):
        global MESSAGES_WAIT_INTERVAL
        global shutdown

        logging.info(
                "let's start 'blindly' generating the messages which take part on a coap session (for a coap client)"
        )

        messages = [] # list of messages to send
        messages.append(MsgTestSuiteAbort())  # message that triggers shutdown
        messages += user_sequence + service_api_calls

        try:
            while not shutdown:
                time.sleep(MESSAGES_WAIT_INTERVAL)
                m = messages.pop()
                publish_message(channel, m)
                logging.info("Publishing in the bus: %s" % repr(m))
        except IndexError:
            time.sleep(5)
            pass

    def stop(self):
        self.connection.close()


if __name__ == '__main__':

    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    logging.getLogger('pika').setLevel(logging.INFO)

    try:
        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
    except KeyError as e:
        AMQP_EXCHANGE = "default"

    try:
        AMQP_URL = str(os.environ['AMQP_URL'])
        p = urlparse(AMQP_URL)
        AMQP_USER = p.username
        AMQP_SERVER = p.hostname
        logging.info(
                "Env variables imported for AMQP connection, User: {0} @ Server: {1} ".format(AMQP_USER, AMQP_SERVER)
        )
    except KeyError as e:
        print('Cannot retrieve environment variables for AMQP connection. Loading defaults..')
        # load default values
        AMQP_URL = "amqp://{0}:{1}@{2}/{3}".format("guest", "guest", "localhost", "/")

    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    channel = connection.channel()
    logging.info("AMQP connection established")



    # in case its not declared
    connection.channel().exchange_declare(exchange=AMQP_EXCHANGE,
                                          type='topic',
                                          durable=True,
                                          )


    # for a typical user input, for a user (coap client) vs automated-iut ( coap server) session type:
    user_sequence = [
        MsgTestSuiteStart(),
        MsgTestCaseSkip(testcase_id='TD_COAP_CORE_02_v01'),
        MsgTestCaseSkip(testcase_id='TD_COAP_CORE_03_v01'),
        MsgTestCaseSkip(testcase_id='TD_COAP_CORE_04_v01'),
        MsgTestCaseStart(),
        MsgStimuliExecuted(),
        MsgVerifyResponse(),
        MsgVerifyResponse(
                verify_response=False,
                description='User indicates that IUT didnt behave as expected '),
        # at this point we should see a TC verdict
        MsgTestCaseRestart(),
    ]

    service_api_calls = [

        # TAT calls
        MsgTestSuiteGetStatus(),
        MsgTestSuiteGetTestCases(),
        MsgInteropTestCaseAnalyze(),
        MsgInteropTestCaseAnalyze(
                testcase_id="TD_COAP_CORE_01",
                testcase_ref="http://f-interop.paris.inria.fr/tests/TD_COAP_CORE_01_v01",
                file_enc="pcap_base64",
                filename="TD_COAP_CORE_01.pcap",
                value=PCAP_empty_base64,
        ),
        MsgInteropTestCaseAnalyze(
                testcase_id="TD_COAP_CORE_01",
                testcase_ref="http://f-interop.paris.inria.fr/tests/TD_COAP_CORE_01_v01",
                file_enc="pcap_base64",
                filename="TD_COAP_CORE_01.pcap",
                value=PCAP_TC_COAP_01_base64,
        ),

        # Sniffer calls
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


    thread_msg_gen = MessageGenerator( AMQP_URL, AMQP_EXCHANGE)
    #thread_inspector.daemon = True
    print("Starting Message Generator thread ")
    thread_msg_gen.start()

    # queues & default exchange declaration
    message_count = 0

    services_queue_name = 'services_queue@%s' % COMPONENT_ID

    channel.queue_delete(queue=services_queue_name)

    channel.queue_declare(queue=services_queue_name)

    channel.queue_bind(exchange=AMQP_EXCHANGE,
                            queue=services_queue_name,
                            routing_key='#')

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(on_request, queue=services_queue_name)

    try:
        channel.start_consuming()
    except Exception as e:
        thread_msg_gen.stop()
        sys.exit(1)


