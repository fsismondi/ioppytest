# -*- coding: utf-8 -*-
import base64
import pika
import json
import uuid
import time
import logging
from threading import Timer

from coap_testing_tool.utils.exceptions import TatError, SnifferError,CoordinatorError, AmqpMessageError
from coap_testing_tool import AMQP_VHOST, AMQP_PASS,AMQP_SERVER,AMQP_USER, AMQP_EXCHANGE
from collections import OrderedDict


def amqp_reply(channel, props, response):
    # check first that sender didnt forget about reply to and corr id
    try:
        reply_to = props.reply_to
        correlation_id = props.correlation_id
        logging.info("reply_to: %s type: %s"%(str(reply_to),str(type(reply_to))))
        logging.info("corr_id: %s type: %s" % (str(correlation_id), str(type(correlation_id))))
    except KeyError:
        logging.error(msg='There is an error on the request, either reply_to or correlation_id not provided')
        return

    logging.debug('Sending reply through the bus: r_key: %s , corr_id: %s'%(reply_to,correlation_id))
    channel.basic_publish(
        body=json.dumps(response, ensure_ascii=False),
        routing_key=reply_to,
        exchange=AMQP_EXCHANGE,
        properties=pika.BasicProperties(
            content_type='application/json',
            correlation_id=correlation_id,
        )
    )

# timeout in seconds
AMQP_REPLY_TOUT = 10

class AmqpSynchronousCallClient:

    def __init__(self, component_id ):
        credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASS)

        # setup blocking connection, do not reuse the conenction from coord, it needs to be a new one!
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=AMQP_SERVER,
            virtual_host=AMQP_VHOST,
            credentials = credentials,
        ))
        self.component_id = component_id

        #this generates a blocking channel
        self.channel = self.connection.channel()
        self.reply_queue_name = 'service_responses@%s'%self.component_id



    def on_response(self, ch, method, props, body):

        ch.basic_ack(delivery_tag=method.delivery_tag)

        if self.corr_id == props.correlation_id:
            self.response = body
        else:
            self.response = None


    def call(self, routing_key, body):

        result = self.channel.queue_declare(queue = self.reply_queue_name)
        self.callback_queue = result.method.queue


        # by convention routing key of answer is routing_key + .reply
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=self.callback_queue,
                                routing_key=routing_key + '.reply')

        self.channel.basic_consume(self.on_response,
                                   no_ack=False,
                                   queue=self.callback_queue)
        self.response = None
        self.corr_id = str(uuid.uuid4())

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_publish(exchange=AMQP_EXCHANGE,
                                   routing_key= routing_key,
                                   properties=pika.BasicProperties(
                                       reply_to= routing_key + '.reply',
                                       correlation_id=self.corr_id,
                                       content_type='application/json',
                                   ),
                                   body=json.dumps(body),
                                   )
        self.timeout = False
        def timeout():
            self.timeout = True

        t = Timer(AMQP_REPLY_TOUT, timeout)
        t.start()
        while self.response is None and not self.timeout:
            time.sleep(1)
            self.connection.process_data_events()

        if self.timeout:
            raise AmqpMessageError("Response timeout for request: \nrouting_key: %s,\nbody%s"
                                   %(routing_key,json.dumps(body)))
        else:
            t.cancel()

        # cleaning up
        self.channel.queue_delete(self.reply_queue_name)

        return json.loads(self.response.decode('utf-8'),object_pairs_hook=OrderedDict)

#this is just an example of usage where we ask the sniffer for a pcap capture and we save it disk after:
if __name__ == '__main__':
    credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASS)
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=AMQP_SERVER,
        virtual_host=AMQP_VHOST,
        credentials=credentials))

    amqpRPCClient = AmqpSynchronousCallClient("dummy_component")

    body = {'_type': 'sniffing.getcapture', 'testcase_id': 'testcase pepito'}
    ret = amqpRPCClient.call("control.sniffing.service", body=body)

    out = ret['value']
    filename = ret['filename']

    # save to file
    with open("./"+filename, "wb") as file2:
        file2.write(base64.b64decode(out))

