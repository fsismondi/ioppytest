# -*- coding: utf-8 -*-
# !/usr/bin/env python3
import pika
import threading
import json
from collections import OrderedDict
import datetime
import signal
import sys
import logging
from coap_testing_tool.utils.rmq_handler import RabbitMQHandler, JsonFormatter
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE, AGENT_NAMES, AGENT_TT_ID

COMPONENT_ID = 'packet_router'
# init logging to stnd output and log files
logger = logging.getLogger(__name__)

# default handler
sh = logging.StreamHandler()
logger.addHandler(sh)

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)
logger.setLevel(logging.DEBUG)

class PacketRouter(threading.Thread):
    AGENT_1_ID = AGENT_NAMES[0]
    AGENT_2_ID = AGENT_NAMES[1]
    AGENT_TT_ID = AGENT_TT_ID

    def __init__(self, conn, routing_table):
        threading.Thread.__init__(self)

        logger.info("Imported agent names of the test session: %s" %str(AGENT_NAMES))

        if routing_table:
            self.routing_table = routing_table
        else:
            # default routing
            # agent_TT is the agent instantiated by the testing tool
            self.routing_table = {
                # first two entries is for a user to user setup
                'data.tun.fromAgent.%s'%PacketRouter.AGENT_1_ID:
                    [
                        'data.tun.toAgent.%s'%PacketRouter.AGENT_2_ID,
                        'data.tun.toAgent.%s'%PacketRouter.AGENT_TT_ID
                    ],
                'data.tun.fromAgent.%s'%PacketRouter.AGENT_2_ID:
                    [
                        'data.tun.toAgent.%s'%PacketRouter.AGENT_1_ID,
                        'data.tun.toAgent.%s'%PacketRouter.AGENT_TT_ID
                    ],

                # entry for a user to automated iut setup (doesnt create any conflict with the previous ones)
                'data.tun.fromAgent.%s'%PacketRouter.AGENT_TT_ID:
                    [
                        'data.tun.toAgent.%s'%PacketRouter.AGENT_1_ID
                    ],
            }

        logger.info('routing table (rkey_src:[rkey_dst]) : {table}'.format(table=json.dumps(self.routing_table)))

        # queues & default exchange declaration
        self.message_count = 0

        self.connection = conn

        self.channel = self.connection.channel()

        queue_name = 'data_packets_queue@%s' % COMPONENT_ID
        self.channel.queue_declare(queue=queue_name)

        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                           queue=queue_name,
                           routing_key='data.tun.fromAgent.#')

        self.channel.basic_publish(
                body=json.dumps({'message': '%s is up!' % COMPONENT_ID, "_type": 'packetrouting.ready'}),
                exchange=AMQP_EXCHANGE,
                routing_key='control.session.bootstrap',
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
        logger.debug("Message sniffed: %s" %(body_dict['_type']))
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
            logger.error('wrong message format, no data field found in : {msg}'.format(msg=json.dumps(body_dict)))
            return

        src_rkey = method.routing_key
        if src_rkey in self.routing_table.keys():
            list_dst_rkey = self.routing_table[src_rkey]
            for dst_rkey in list_dst_rkey:
                # resend to dst_rkey
                self.channel.basic_publish(
                        body=json.dumps({'_type': 'packet.to_inject.raw', 'data': data}),
                        routing_key=dst_rkey,
                        exchange=AMQP_EXCHANGE,
                        properties=pika.BasicProperties(
                                content_type='application/json',
                        )
                )

                logger.info("Routing packet (%d) from topic: %s to topic: %s"%(self.message_count,src_rkey,dst_rkey))

        else:
            logger.error('No known route for r_key source: {r_key}'.format(r_key=src_rkey))
            return


    def run(self):
        self.channel.start_consuming()
        logger.info('Bye byes!')




###############################################################################

if __name__ == '__main__':

    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    channel = connection.channel()

    def signal_int_handler(channel):
        # FINISHING... let's send a goodby message
        msg = {
            'message': '{component} is out! Bye bye..'.format(component=COMPONENT_ID),
            "_type": '{component}.shutdown'.format(component=COMPONENT_ID)
        }
        channel.basic_publish(
                body=json.dumps(msg),
                routing_key='control.session.info',
                exchange=AMQP_EXCHANGE,
                properties=pika.BasicProperties(
                        content_type='application/json',
                )
        )

        logger.info('got SIGINT. Bye bye!')

        sys.exit(0)


    signal.signal(signal.SIGINT, signal_int_handler)

    # in case its not declared
    connection.channel().exchange_declare(exchange=AMQP_EXCHANGE,
                             type='topic',
                             durable=True,
                             )

    # start amqp router thread
    r = PacketRouter(connection,None)
    r.start()




