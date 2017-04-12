# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import pika
import threading
import logging
import subprocess
import datetime
import os
import signal
from coap_testing_tool.utils.event_bus_messages import *
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE

COMPONENT_ID = 'finterop_coap_client_test_executor'

# timeout in seconds
STIMULI_HANDLER_TOUT = 10

IUT_CMD = [
    'python',
    'coap_testing_tool/automated_implementations/coap_client_coapthon/CoAPthon/coapclient.py'
]


# mapping message's stimuli id -> CoAPthon (coap client) commands
coap_client_tc_stimuli_commands = {
'TD_COAP_CORE_01_v01_step_01' :  IUT_CMD + ['-o', 'GET', '-p', 'coap://127.0.0.1:5683/test', ],
'TD_COAP_CORE_01_v01_step_02' :  IUT_CMD + ['-o', 'GET', '-p', 'coap://127.0.0.1:5683/test', ],
}

class AmqpListener(threading.Thread):

    def __init__(self, conn):
        threading.Thread.__init__(self)
        # queues & default exchange declaration
        self.message_count = 0

        self.connection = conn

        self.channel = connection.channel()

        services_queue_name = 'services_queue@%s' % COMPONENT_ID
        self.channel.queue_declare(queue=services_queue_name, auto_delete=True)

        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                           queue=services_queue_name,
                           routing_key='control.testcoordination')
        # Hello world message
        self.channel.basic_publish(
                routing_key='control.%s.info' % COMPONENT_ID,
                exchange=AMQP_EXCHANGE,
                properties=pika.BasicProperties(
                        content_type='application/json',
                ),
                body=json.dumps(
                    {
                        '_type': '%s.info' %(COMPONENT_ID),
                        'value': '%s is up!'%(COMPONENT_ID),
                    }
                ),
        )

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.on_request, queue=services_queue_name)

    def stop(self):
        self.channel.stop_consuming()

    def on_request(self, ch, method, props, body):
        # obj hook so json.loads respects the order of the fields sent -just for visualization purposeses-
        req_body_dict = json.loads(body.decode('utf-8'),object_pairs_hook=OrderedDict)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logging.info("Message sniffed: %s, body: %s" % (json.dumps(req_body_dict), str(body)))
        self.message_count += 1

        props_dict={
            'content_type': props.content_type,
            'content_encoding': props.content_encoding,
            'headers': props.headers,
            'delivery_mode': props.delivery_mode,
            'priority': props.priority,
            'correlation_id': props.correlation_id,
            'reply_to': props.reply_to,
            'expiration': props.expiration,
            'message_id': props.message_id,
            'timestamp': props.timestamp,
            'user_id': props.user_id,
            'app_id': props.app_id,
            'cluster_id': props.cluster_id,
        }
        #let's get rid of values which are empty
        props_dict_only_non_empty_values = {k: v for k, v in props_dict.items() if v is not None}

        print('\n* * * * * * MESSAGE SNIFFED (%s) * * * * * * *'%self.message_count)
        print("TIME: %s"%datetime.datetime.time(datetime.datetime.now()))
        print(" - - - ")
        print("ROUTING_KEY: %s" % method.routing_key)
        print(" - - - ")
        print("HEADERS: %s" % props.headers)
        print(" - - - ")
        print("PROPS: %s" %json.dumps(props_dict_only_non_empty_values))
        print(" - - - ")
        print('BODY %s' % json.dumps(req_body_dict))
        print(" - - - ")
        #print("ERRORS: %s" % )
        print('* * * * * * * * * * * * * * * * * * * * * \n')

        if props.content_type != "application/json":
            print('* * * * * * API VALIDATION WARNING * * * * * * * ')
            print("props.content_type : " + str(props.content_type))
            print("application/json was expected")
            print('* * * * * * * * * * * * * * * * * * * * *  \n')

        if '_type' not in req_body_dict.keys():
            print('* * * * * * API VALIDATION WARNING * * * * * * * ')
            print("no < _type > field found")
            print('* * * * * * * * * * * * * * * * * * * * *  \n')


        message = Message.from_json(body.decode('utf-8'))

        print(message)

        if message is None:
            return

        if message._type == 'testcoordination.step.execute':
            if message.step_id in coap_client_tc_stimuli_commands:
                self._execute_stimuli( message.step_id , coap_client_tc_stimuli_commands[message.step_id] )
                FINISH and thest the command list

    def _execute_stimuli(self, stimuli_step_id, cmd):
        logging.info('spawning process with : %s' %cmd)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        proc.wait(timeout = STIMULI_HANDLER_TOUT)
        output=''
        while proc.poll() is None:
            output += str(proc.stdout.readline())
        output += str(proc.stdout.read())
        logging.info('%s executed' % stimuli_step_id)
        logging.info('process stdout: %s' % output)

        self._publish_event(MsgStimuliExecuted())

    def _publish_event(self, message):

        properties = pika.BasicProperties(
                content_type='application/json',
        )

        channel.basic_publish(
                exchange=AMQP_EXCHANGE,
                routing_key=message.routing_key,
                properties=properties,
                body=message.to_json(),
        )

    def run(self):
        print("Starting thread listening on the event bus")
        self.channel.start_consuming()
        print('Bye byes!')


if __name__ == '__main__':

    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

    # lets create connection
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

    channel = connection.channel()

    # in case exchange not not declared
    connection.channel().exchange_declare(exchange=AMQP_EXCHANGE,
                                          type='topic',
                                          durable=True,
                                          )




    # start amqp listener thread
    amqp_listener = AmqpListener(connection)
    amqp_listener.start()

    amqp_listener.join()
    connection.close()


    # tests:
    #amqp_listener._handle_TD_COAP_CORE_01_stimuli()
