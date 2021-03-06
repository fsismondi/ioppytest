# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import os
import sys
import json
import errno
import pika
import time
import traceback
import logging
import argparse
from threading import Timer

from ioppytest import (AMQP_URL, AMQP_EXCHANGE, TEST_DESCRIPTIONS_DICT, TEST_DESCRIPTIONS_CONFIGS_DICT, LOGGER_FORMAT,
                       LOG_LEVEL,DATADIR, TMPDIR, LOGDIR, TD_DIR, RESULTS_DIR, PCAP_DIR)
from ioppytest.test_coordinator.coordinator import Coordinator
from event_bus_utils.rmq_handler import RabbitMQHandler, JsonFormatter
from event_bus_utils import publish_message
from messages import MsgTestingToolReady, MsgTestingToolComponentReady, Message

COMPONENT_ID = 'test_coordinator|main'
logging.basicConfig(format=LOGGER_FORMAT)

# init logging to stnd output and log files
logger = logging.getLogger(COMPONENT_ID)
logger.setLevel(LOG_LEVEL)

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)

# make pika logger less verbose
logging.getLogger('pika').setLevel(logging.WARNING)

TT_check_list = [
    'dissection',
    'analysis',
    'sniffing',
    'testcoordination',
    'packetrouting',
]
# time to wait for components to send for READY signal
READY_SIGNAL_TOUT = 45

if __name__ == '__main__':

    no_component_checks = None
    testsuite = None
    ted_tc_file = None
    ted_config_file = None

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("testsuite", help="Test Suite", choices=list(TEST_DESCRIPTIONS_DICT.keys()))
        parser.add_argument("-ncc", "--no_component_checks", help="Do not check if other processes send ready message",
                            action="store_true")
        args = parser.parse_args()

        testsuite = args.testsuite
        no_component_checks = args.no_component_checks

        if testsuite in TEST_DESCRIPTIONS_DICT and testsuite in TEST_DESCRIPTIONS_CONFIGS_DICT:
            ted_tc_file = TEST_DESCRIPTIONS_DICT[testsuite]
            ted_config_file = TEST_DESCRIPTIONS_CONFIGS_DICT[testsuite]
            logger.info("Starting test suite: %s" % ted_tc_file)
        else:
            logger.error("Error , please see coordinator help (-h)")
            sys.exit(1)
    except Exception as e:
        logger.error(e)

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

    bootstrap_q_name = 'bootstrapping'
    bootstrap_q = channel.queue_declare(queue=bootstrap_q_name, auto_delete=True)

    # starting verification of the testing tool components
    channel.queue_bind(
        exchange=AMQP_EXCHANGE,
        queue='bootstrapping',
        routing_key=MsgTestingToolComponentReady.routing_key,
    )

    msg = MsgTestingToolComponentReady(
        component='testcoordination'
    )
    publish_message(connection, msg)

    if no_component_checks:
        logger.info('Skipping testing tool component readiness checks')
    else:
        def on_ready_signal(ch, method, props, body):
            ch.basic_ack(delivery_tag=method.delivery_tag)
            event = Message.load_from_pika(method, props, body)

            if isinstance(event, MsgTestingToolComponentReady):
                component = event.component
                logger.info('ready signals received %s' % component)
                if component in TT_check_list:
                    TT_check_list.remove(component)
                    return
            elif isinstance(event, MsgTestingToolReady):  # listen to self generated event
                logger.info('all signals processed')
                channel.queue_delete('bootstrapping')
                return
            else:
                pass


        # bind on_ready_signal callback to signals queue
        channel.basic_consume(on_message_callback=on_ready_signal,
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

        while len(TT_check_list) != 0 and not timeout:  # blocking until timeout!
            time.sleep(0.1)
            connection.process_data_events()

        if timeout:
            logger.error("Some components havent sent READY signal: %s" % str(TT_check_list))
            sys.exit(1)

        assert len(TT_check_list) == 0
        logger.info('All components ready')

    # clean up
    channel.queue_delete(bootstrap_q_name)

    # lets start the test coordination
    try:
        logger.info(
            'Starting test-coordinator for test suite: \n\t%s\n\t%s\n\t%s' % (ted_tc_file, ted_config_file, testsuite))
        coordinator = Coordinator(AMQP_URL, AMQP_EXCHANGE, ted_tc_file, ted_config_file, testsuite)
        coordinator.bootstrap()
        publish_message(connection, MsgTestingToolReady())

    except Exception as e:
        # cannot emit AMQP messages for the fail
        error_msg = str(e)
        logger.error(' Critical exception found: %s , traceback: %s' % (error_msg, traceback.format_exc()))
        logger.debug(traceback.format_exc())
        sys.exit(1)

    # # # RUN TEST COORDINATION COMPONENT # # #

    connection.close()

    try:
        logger.info('Starting coordinator..')
        # start consuming messages
        coordinator.run()
        logger.info('Finishing coordinator..')

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
            }),
            exchange=AMQP_EXCHANGE,
            routing_key='error',
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )
        # close AMQP connection
        connection.close()

        sys.exit(1)
