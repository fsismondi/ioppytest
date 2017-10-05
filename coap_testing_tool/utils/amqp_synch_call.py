# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import pika
import time
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE
from coap_testing_tool.utils.event_bus_messages import *


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


def amqp_request(channel, request_message: Message, component_id: str):
    # NOTE: channel must be a pika channel

    # check first that sender didnt forget about reply to and corr id
    assert request_message.reply_to
    assert request_message.correlation_id

    response = None

    reply_queue_name = 'amqp_rpc_%s@%s' % (str(uuid.uuid4())[:8], component_id)

    result = channel.queue_declare(queue=reply_queue_name, auto_delete=True)

    callback_queue = result.method.queue

    # bind and listen to reply_to topic
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
    retries_left = 10

    while retries_left > 0:
        time.sleep(0.5)
        method, props, body = channel.basic_get(reply_queue_name)
        if method:
            channel.basic_ack(method.delivery_tag)
            if hasattr(props, 'correlation_id') and props.correlation_id == request_message.correlation_id:
                break
        retries_left -= 1

    if retries_left > 0:

        body_dict = json.loads(body.decode('utf-8'), object_pairs_hook=OrderedDict)
        response = MsgReply(request_message, **body_dict)

    else:
        # clean up
        channel.queue_delete(reply_queue_name)
        raise TimeoutError(
                "Response timeout! rkey: %s , request type: %s" % (
                    request_message.routing_key,
                    request_message._type
                )
        )

    # clean up
    channel.queue_delete(reply_queue_name)

    return response


if __name__ == '__main__':
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    m = MsgSniffingGetCapture()
    r = amqp_request(connection.channel(), m, 'someImaginaryComponent')
    print(repr(r))
