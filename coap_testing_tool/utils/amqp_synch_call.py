# -*- coding: utf-8 -*-
import base64
import pika
import json
import uuid
import time
import logging
from threading import Timer

from coap_testing_tool.utils.exceptions import TatError, SnifferError,CoordinatorError, AmqpMessageError
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE
from collections import OrderedDict
from coap_testing_tool.utils.event_bus_messages import *

# timeout in seconds
AMQP_REPLY_TOUT = 10


def amqp_reply(channel, props, response):
    """
    DEPRICATED! Just generate a reply message using MsgReply class
    and use publish_message method

    :param channel:
    :param props:
    :param response:
    :return:
    """
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

def publish_message(channel, message):
    """ Published which uses message object metadata

    :param channel:
    :param message:
    :return:
    """

    properties = pika.BasicProperties(**message.get_properties())

    channel.basic_publish(
            exchange=AMQP_EXCHANGE,
            routing_key=message.routing_key,
            properties=properties,
            body=message.to_json(),
    )

def amqp_request(request_message : Message, component_id : str):
    # check first that sender didnt forget about reply to and corr id
    assert(request_message.reply_to)
    assert (request_message.correlation_id)

    # setup blocking connection, do not reuse the conection from coord, it needs to be a new one
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    response = None

    channel = connection.channel()
    reply_queue_name = 'amqp_rpc_%s@%s' %(str(uuid.uuid4())[:8],component_id)

    result = channel.queue_declare(queue=reply_queue_name, auto_delete=True)

    callback_queue = result.method.queue

    # by convention routing key of answer is routing_key + .reply
    channel.queue_bind(
            exchange=AMQP_EXCHANGE,
            queue=callback_queue,
            routing_key=request_message.reply_to
    )

    channel.basic_publish(
            exchange=AMQP_EXCHANGE,
            routing_key=request_message.routing_key,
            properties=pika.BasicProperties(**request_message.get_properties()),
            body=request_message.to_json(),
    )

    time.sleep(0.2)
    max_retries = 5

    method, props, body = channel.basic_get(reply_queue_name)

    while max_retries > 0:
        if hasattr(props, 'correlation_id') and props.correlation_id == request_message.correlation_id:
            break
        method, props, body = channel.basic_get(reply_queue_name)
        max_retries -= 1
        time.sleep(0.5)

    if max_retries > 0 :
        body_dict = json.loads(body.decode('utf-8'),object_pairs_hook=OrderedDict)
        response = MsgReply(request_message, **body_dict)

    else:
        raise AmqpMessageError("Response timeout! rkey: %s , request type: %s"
                               %(
                                    request_message.routing_key,
                                    request_message._type
                               )
                               )

    # cleaning up
    channel.queue_delete(reply_queue_name)
    connection.close()

    return response





class AmqpSynchronousCallClient:

    def __init__(self, component_id ):
        # setup blocking connection, do not reuse the conection from coord, it needs to be a new one
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.component_id = component_id

        # this generates a blocking channel
        self.channel = self.connection.channel()
        self.reply_queue_name = 'service_responses@%s'%self.component_id

    def on_response(self, ch, method, props, body):
        ch.basic_ack(delivery_tag=method.delivery_tag)
        if self.corr_id == props.correlation_id:
            self.response = body
        else:
            self.response = None


    def call(self, routing_key, body):
        result = self.channel.queue_declare(queue = self.reply_queue_name, auto_delete=True)
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

if __name__ == '__main__':

    #this is just an example of usage where we ask the sniffer for a pcap capture and we save it disk after:
    # connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    # amqpRPCClient = AmqpSynchronousCallClient("dummy_component")
    #
    # body = {'_type': 'sniffing.getcapture', 'testcase_id': 'testcase pepito'}
    # ret = amqpRPCClient.call("control.sniffing.service", body=body)
    #
    # out = ret['value']
    # filename = ret['filename']
    #
    # # save to file
    # with open("./"+filename, "wb") as file2:
    #     file2.write(base64.b64decode(out))

    m = MsgSniffingGetCapture()
    r = amqp_request(m, 'someImaginaryComponent')
    print(repr(r))

