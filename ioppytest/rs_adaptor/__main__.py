#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import pika
import json
import logging
import traceback

from ioppytest import LOG_LEVEL, LOGGER_FORMAT, AMQP_URL, AMQP_EXCHANGE

from messages import Message, MsgReportSaveRequest, MsgReportSaveReply, MsgTestCaseVerdict, MsgTestSuiteReport
from event_bus_utils import AmqpSynchCallTimeoutError, AmqpListener, amqp_request
from event_bus_utils.rmq_handler import RabbitMQHandler, JsonFormatter

COMPONENT_ID = 'rs_adaptor'

TESTING_TOOL_TOPIC_SUBSCRIPTIONS = [
    MsgTestCaseVerdict.routing_key,
    MsgTestSuiteReport.routing_key
]

# init logging with stnd output and amqp handlers
logging.basicConfig(format=LOGGER_FORMAT)
logger = logging.getLogger("%s" % COMPONENT_ID)
logger.setLevel(LOG_LEVEL)

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)

logging.getLogger('pika').setLevel(logging.WARNING)


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def save_result_into_RS_db(message: Message):
    if isinstance(message, MsgTestSuiteReport):
        m_data = message.tc_results  # this is a list
        m_type = "final"
    elif isinstance(message, MsgTestCaseVerdict):
        m_data = message.to_dict()
        m_type = "intermediate"
    else:
        raise TypeError("Expecting Report or TC verdict message")

    m = MsgReportSaveRequest(
        type=m_type,
        data=m_data,
    )
    logger.info("Sending %s results to RS" % m_type)
    try:

        reply = amqp_request(
            connection=pika.BlockingConnection(pika.URLParameters(AMQP_URL)),
            request_message=m,
            component_id=COMPONENT_ID,
            retries=3,
            use_message_typing=True,
        )

    except AmqpSynchCallTimeoutError as tout:
        logger.warning("Request for %s timed out. Is RS up?" % type(m))
        return

    if not reply or not reply.ok:
        logger.warning("Couldn't save results, got response: %s " % repr(reply))
        return

    logger.info("Successful %s results save into RS" % m_type)


def main():
    tt_amqp_listener_thread = AmqpListener(
        amqp_url=AMQP_URL,
        amqp_exchange=AMQP_EXCHANGE,
        topics=TESTING_TOOL_TOPIC_SUBSCRIPTIONS,
        use_message_typing=True,
        callback=save_result_into_RS_db
    )

    tt_amqp_listener_thread.setName('TT_to_RS_results_forwarder_thread')

    try:
        tt_amqp_listener_thread.start()
        logger.info('%s listening to the event bus...' % COMPONENT_ID)
        tt_amqp_listener_thread.join()

    except AmqpSynchCallTimeoutError as tout:
        err_msg = "UI response timeout, entering default testsuite configuration. \nException: %s" % str(tout)
        logger.error(err_msg)

    except KeyboardInterrupt:
        logger.info('user interruption captured, exiting..')
        logger.info('%s stopping..' % COMPONENT_ID)
        tt_amqp_listener_thread.stop()  # thread
        return

    except Exception as err:
        logger.error(err)
        logger.error(traceback.format_exc())
        raise err


if __name__ == '__main__':

    # setup amqp connection
    try:
        logger.info('Setting up AMQP connection..')
        # setup AMQP connection
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

    except pika.exceptions.ConnectionClosed as cc:
        logger.error(' AMQP cannot be established, is message broker up? \n More: %s' % traceback.format_exc())
        sys.exit(1)

    channel = connection.channel()

    try:
        logger.info('Starting %s component..' % COMPONENT_ID)
        # start main loop
        main()
        logger.info('%s component stopped' % COMPONENT_ID)

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
        channel.basic_publish(
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
