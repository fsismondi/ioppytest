# -*- coding: utf-8 -*-
import base64
import pika
import json
import uuid
import time

from coap_testing_tool.utils.exceptions import TatError, SnifferError,CoordinatorError, AmqpMessageError
from coap_testing_tool import AMQP_VHOST, AMQP_PASS,AMQP_SERVER,AMQP_USER, AMQP_EXCHANGE


class AmqpSynchronousCallClient:

    # timeout in seconds
    AMQP_REPLY_TOUT = 10

    def __init__(self, component_id):
        self.component_id = component_id

        credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASS)

        self.connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=AMQP_SERVER,
            virtual_host=AMQP_VHOST,
            credentials = credentials))

        self.channel = self.connection.channel()

        result = self.channel.queue_declare(queue='services_replies@%s'%self.component_id)
        self.callback_queue = result.method.queue


    def on_response(self, ch, method, props, body):
        # logging.info('* * * * * * AMQP MESSAGE RECEIVED * * * * * * *')
        # logging.info('BODY %s || PROPS %s' % (body, props))
        # logging.info('* * * * * * * * * * * * * * * * * * * * * \n')
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, routing_key, body):
        # by convention routing key of answer is routing_key + .reply
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=self.callback_queue,
                                routing_key=routing_key + '.reply')

        self.channel.basic_consume(self.on_response,
                                   no_ack=True,
                                   queue=self.callback_queue)
        self.response = None
        self.corr_id = str(uuid.uuid4())
        # TODO get as param the exchange and COMPONENT_ID
        self.channel.basic_publish(exchange='default',
                                   routing_key= routing_key,
                                   properties=pika.BasicProperties(
                                       reply_to= routing_key + '.reply',
                                       correlation_id=self.corr_id,
                                   ),
                                   body=json.dumps(body),
                                   )

        timer = AMQP_REPLY_TOUT/0.1 #if sleep 0.1s => timout trigger after 10secs
        while self.response is None and not timer < 0:
            self.connection.process_data_events()
            time.sleep(0.1)
            timer -= 1
        if timer < 0:
            raise AmqpMessageError("Coordinator response timeout")
        return json.loads(self.response.decode('utf-8'))

#this is just an example of usage where we ask the sniffer for a pcap capture and we save it disk after:
if __name__ == '__main__':
    amqpRPCClient = AmqpSynchronousCallClient("dummy_component")
    body = {'_type': 'sniffing.getCapture', 'testcase_id': 'testcase pepito'}
    ret = amqpRPCClient.call("control.sniffing.service", body=body)

    out = ret['value']
    filename = ret['filename']

    # save to file
    with open("./"+filename, "wb") as file2:
        file2.write(base64.b64decode(out))

