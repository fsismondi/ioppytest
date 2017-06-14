# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import logging
from threading import Timer
from coap_testing_tool.test_coordinator.coordinator import *
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE
from coap_testing_tool import DATADIR, TMPDIR, LOGDIR, TD_DIR
from coap_testing_tool.utils.rmq_handler import RabbitMQHandler, JsonFormatter

COMPONENT_ID = 'test_coordinator'

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

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

# make pika logger less verbose
logging.getLogger('pika').setLevel(logging.INFO)

TT_check_list = [
    'dissection',
    'analysis',
    'sniffing',
    'testcoordination',
    'packetrouting',
    'agent_TT',
]
# time to wait for components to send for READY signal
READY_SIGNAL_TOUT = 15

if __name__ == '__main__':

    # generate dirs
    for d in TMPDIR, DATADIR, LOGDIR, RESULTS_DIR, PCAP_DIR:
        try:
            os.makedirs(d)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    # setup amqp connection
    try:
        logger.info('Setting up AMQP connection..')
        # setup AMQP connection
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

    except pika.exceptions.ConnectionClosed as cc:
        logger.error(' AMQP cannot be established, is message broker up? \n More: %s' % traceback.format_exc())
        sys.exit(1)

    channel = connection.channel()

    # in case exchange not declared
    channel.exchange_declare(
            exchange=AMQP_EXCHANGE,
            type='topic',
            durable=True,
    )

    bootstrap_q = channel.queue_declare(queue='bootstrapping', auto_delete=True)

    channel.queue_bind(
            exchange=AMQP_EXCHANGE,
            queue='bootstrapping',
            routing_key='control.session',
    )

    # starting verification of the testing tool components
    msg = MsgTestingToolComponentReady(
            component='testcoordination'
    )
    publish_message(channel, msg)


    def on_ready_signal(ch, method, props, body):
        ch.basic_ack(delivery_tag=method.delivery_tag)

        event = Message.from_json(body)

        if isinstance(event, MsgTestingToolComponentReady):
            component = event.component
            logger.info('ready signals received %s' % component)
            if component in TT_check_list:
                TT_check_list.remove(component)
                return

        elif isinstance(event, MsgTestingToolReady):
            logger.info('all signals processed')
            channel.queue_delete('bootstrapping')
            return
        else:
            pass

    # bind callback function to signal queue
    channel.basic_consume(on_ready_signal,
                          no_ack=False,
                          queue='bootstrapping')

    logger.info('Waiting components ready signal... signals not checked:' + str(TT_check_list))

    # wait for all testing tool component's signal
    timeout = False

    def timeout_f():
        global timeout
        timeout = True

    t = Timer(READY_SIGNAL_TOUT, timeout_f)
    t.start()

    while len(TT_check_list) != 0 and not timeout:
        time.sleep(0.3)
        connection.process_data_events()

    if timeout:
        logger.error("Some components havent sent READY signal: %s" % str(TT_check_list))
        sys.exit(1)

    logger.info('All components ready')
    assert len(TT_check_list) == 0
    publish_message(channel, MsgTestingToolReady())

    # lets start the test suite coordination phase

    try:
        logger.info('Starting test-coordinator..')
        coordinator = Coordinator(connection, TD_COAP, TD_COAP_CFG)

    except Exception as e:
        # cannot emit AMQP messages for the fail
        error_msg = str(e)
        logger.error(' Critical exception found: %s , traceback: %s' % (error_msg, traceback.format_exc()))
        logger.debug(traceback.format_exc())
        sys.exit(1)

    ### RUN TEST COORDINATION COMPONENT ###

    try:
        logger.info('Starting coordinator execution ..')
        # start consuming messages
        coordinator.run()
        logger.info('Finishing...')

    except pika.exceptions.ConnectionClosed as cc:
        logger.error(' AMQP connection closed: %s' % str(cc))
        sys.exit(1)

    except KeyboardInterrupt as KI:
        # close AMQP connection
        connection.close()
        sys.exit(1)

    except Exception as e:
        error_msg = str(e)
        logger.error(' Critical exception found: %s, traceback: %s' % (error_msg, traceback.format_exc()))
        logger.debug(traceback.format_exc())

        # lets push the error message into the bus
        coordinator.channel.basic_publish(
                body=json.dumps({
                    'traceback': traceback.format_exc(),
                    'message': error_msg,
                    '_type': 'testcoordination.error',
                }),
                exchange=AMQP_EXCHANGE,
                routing_key='control.session.error',
                properties=pika.BasicProperties(
                        content_type='application/json',
                )
        )
        # close AMQP connection
        connection.close()

        sys.exit(1)
