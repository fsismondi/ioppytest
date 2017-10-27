import os
import pika

# for using it as library and as a __main__
try:
    from messages import *
except:
    from .messages import *

VERSION = '0.0.6'
AMQP_EXCHANGE = 'amq.topic'


def publish_message(connection, message):
    """
    Publishes message into the correct topic (uses Message object metadata)
    Creates temporary channel on it's own
    Connection must be a pika.BlockingConnection
    """
    channel = None

    try:
        channel = connection.channel()

        properties = pika.BasicProperties(**message.get_properties())

        channel.basic_publish(
            exchange=AMQP_EXCHANGE,
            routing_key=message.routing_key,
            properties=properties,
            body=message.to_json(),
        )

    finally:
        if channel and channel.is_open:
            channel.close()


def amqp_request(connection, request_message, component_id):
    """
    Publishes message into the correct topic (uses Message object metadata)
    Returns reply message.
    Uses reply_to and corr id amqp's properties for matching the reply
    Creates temporary channel, and queues on it's own
    Connection must be a pika.BlockingConnection
    """

    # check first that sender didnt forget about reply to and corr id
    assert request_message.reply_to
    assert request_message.correlation_id

    channel = None

    try:
        channel = connection.channel()

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

        return response

    finally:
        if channel and channel.is_open:
            # clean up
            channel.queue_delete(reply_queue_name)
            channel.close()


if __name__ == '__main__':

    try:
        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
    except KeyError as e:
        AMQP_EXCHANGE = "amq.topic"

    try:
        from urllib.parse import urlparse

        AMQP_URL = str(os.environ['AMQP_URL'])
        p = urlparse(AMQP_URL)
        AMQP_USER = p.username
        AMQP_PASS = p.password
        AMQP_SERVER = p.hostname
        AMQP_VHOST = p.path.strip('/')

        print('Env vars for AMQP connection succesfully imported')

    except KeyError as e:

        print('Cannot retrieve environment variables for AMQP connection. Loading defaults..')
        # load default values
        AMQP_SERVER = "localhost"
        AMQP_USER = "guest"
        AMQP_PASS = "guest"
        AMQP_VHOST = "/"
        AMQP_URL = "amqp://{0}:{1}@{2}/{3}".format(AMQP_USER, AMQP_PASS, AMQP_SERVER, AMQP_VHOST)

    print(json.dumps(
        {
            'server': AMQP_SERVER,
            'session': AMQP_VHOST,
            'user': AMQP_USER,
            'pass': '#' * len(AMQP_PASS),
            'exchange': AMQP_EXCHANGE
        }
    ))

    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    m = MsgSniffingGetCapture()
    r = amqp_request(connection, m, 'someImaginaryComponent')
    print(repr(r))
