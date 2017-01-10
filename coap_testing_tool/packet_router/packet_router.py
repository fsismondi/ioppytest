# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import pika
import threading
import logging
import time
import json
from datetime import timedelta
import traceback
import uuid
from collections import OrderedDict
import datetime
import os
import signal

COMPONENT_ID = 'packet_router'

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')

LOGGER = logging.getLogger(COMPONENT_ID)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

class PacketRouter(threading.Thread):

    def __init__(self, conn, routing_table):
        threading.Thread.__init__(self)

        if routing_table:
            self.routing_table = routing_table
        else:
            #default routing
            self.routing_table = {
                'data.tun.fromAgent.agent1': 'data.tun.toAgent.agent2',
                'data.tun.fromAgent.agent2': 'data.tun.toAgent.agent1',
            }
        logging.info('routing table: {table}'.format(table=json.dumps(self.routing_table)))

        # queues & default exchange declaration
        self.message_count = 0

        self.connection = conn

        self.channel = connection.channel()

        queue_name = 'data_packets_queue@%s' % COMPONENT_ID
        self.channel.queue_declare(queue=queue_name)

        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                           queue=queue_name,
                           routing_key='data.tun.fromAgent.#')

        # Hello world message
        self.channel.basic_publish(
                body=json.dumps({'_type': 'packet_router.info', 'value': 'packet router is up!'}),
                routing_key='control.packetrouter.info',
                exchange=AMQP_EXCHANGE,
                properties=pika.BasicProperties(
                        content_type='application/json',
                )
        )

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.on_request, queue=queue_name)

    def stop(self):
        self.channel.stop_consuming()

    def on_request(self, ch, method, props, body):
        # obj hook so json.loads respects the order of the fields sent -just for visualization purposeses-
        body_dict = json.loads(body.decode('utf-8'),object_pairs_hook=OrderedDict)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logging.info("Message sniffed: %s, body: %s" % (str(body_dict), str(body)))
        self.message_count += 1

        print('\n* * * * * * MESSAGE SNIFFED (%s) * * * * * * *'%self.message_count)
        print("TIME: %s"%datetime.datetime.time(datetime.datetime.now()))
        print(" - - - ")
        print("ROUTING_KEY: %s" % method.routing_key)
        print(" - - - ")
        print("HEADERS: %s" % props.headers)
        print(" - - - ")
        print("PROPS: %s" %json.dumps(
                    {
                        'content_type' : props.content_type,
                        'content_encoding' : props.content_encoding,
                        'headers' : props.headers,
                        'delivery_mode' : props.delivery_mode,
                        'priority' : props.priority,
                        'correlation_id' : props.correlation_id,
                        'reply_to' : props.reply_to,
                        'expiration' : props.expiration,
                        'message_id' : props.message_id,
                        'timestamp' : props.timestamp,
                        'user_id' : props.user_id,
                        'app_id' : props.app_id,
                        'cluster_id' : props.cluster_id,
                    }
                )
              )
        print(" - - - ")
        print('BODY %s' % json.dumps(body_dict))
        print(" - - - ")
        #print("ERRORS: %s" % )
        print('* * * * * * * * * * * * * * * * * * * * * \n')

        # let's route the message to the right agent

        try:
            data = body_dict['data']
        except:
            logging.error('wrong message format, no data field found in : {msg}'.format(msg=json.dumps(body_dict)))
            return

        src_rkey = method.routing_key
        if src_rkey in self.routing_table.keys():
            dst_rkey = self.routing_table[src_rkey]
        else:
            logging.error('No know route for r_key source: {r_key}'.format(r_key=src_rkey))
            return

        # resend with dst_rkey
        self.channel.basic_publish(
                body=json.dumps({'_type': 'packet.to_inject.raw', 'data': data}),
                routing_key=dst_rkey,
                exchange=AMQP_EXCHANGE,
                properties=pika.BasicProperties(
                        content_type='application/json',
                )
        )


        print('\n* * * * * * ROUTING MESSAGE (%s) * * * * * * *'%self.message_count)
        print("TIME: %s"%datetime.datetime.time(datetime.datetime.now()))
        print(" - - - ")
        print("ROUTING_KEY SRC: %s" %src_rkey)
        print("ROUTING_KEY DST: %s" %dst_rkey)
        print(" - - - ")
        #print("ERRORS: %s" % )
        print('* * * * * * * * * * * * * * * * * * * * * \n')



    def run(self):
        print("Starting thread listening on the event bus")
        self.channel.start_consuming()
        print('Bye byes!')




###############################################################################

if __name__ == '__main__':


    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)


    # rewrite default values with ENV variables
    try:
        AMQP_SERVER = str(os.environ['AMQP_SERVER'])
        AMQP_USER = str(os.environ['AMQP_USER'])
        AMQP_PASS = str(os.environ['AMQP_PASS'])
        AMQP_VHOST = str(os.environ['AMQP_VHOST'])
        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])

        print('Env vars for AMQP connection succesfully imported')
        print(json.dumps(
                {
                    'server': AMQP_SERVER,
                    'session': AMQP_VHOST,
                    'user': AMQP_USER,
                    'pass': '#' * len(AMQP_PASS),
                    'exchange':AMQP_EXCHANGE
                }
        ))

    except KeyError as e:
        print(' Cannot retrieve environment variables for AMQP connection')

    credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASS)
    connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=AMQP_SERVER,
            virtual_host=AMQP_VHOST,
            credentials=credentials))

    channel = connection.channel()

    # in case its not declared
    connection.channel().exchange_declare(exchange=AMQP_EXCHANGE,
                             type='topic',
                             durable=True,
                             )



    # start amqp router thread
    r = PacketRouter(connection,None)
    r.start()




