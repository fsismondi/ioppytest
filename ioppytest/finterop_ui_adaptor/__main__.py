#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import signal
import pika
import logging
import argparse
import threading
from queue import Queue

from ioppytest import AMQP_URL, AMQP_EXCHANGE, LOG_LEVEL, LOGGER_FORMAT
from ioppytest.utils.event_bus_utils import AmqpListener, amqp_request
from ioppytest.utils.rmq_handler import RabbitMQHandler, JsonFormatter
from ioppytest.utils.messages import *
from ioppytest.finterop_ui_adaptor import COMPONENT_ID, STDOUT_MAX_STRING_LENGTH, MESSAGES_NOT_TO_BE_ECHOED
from ioppytest.finterop_ui_adaptor.message_translators import (DummySessionMessageTranslator,
                                                               CoMISessionMessageTranslator,
                                                               CoAPSessionMessageTranslator,
                                                               SixLoWPANSessionMessageTranslator,
                                                               OneM2MSessionMessageTranslator)

logging.basicConfig(
    level=LOG_LEVEL,
    format=LOGGER_FORMAT
)

logging.getLogger('pika').setLevel(logging.WARNING)

# init logging to stnd output and log files
logger = logging.getLogger("%s|%s" % (COMPONENT_ID, 'amqp_connector'))

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)

TESTING_TOOL_TOPIC_SUBSCRIPTIONS = [
    'testsuite.#',
    'testingtool.#',
    'session.#',
    'log.#'
    'fromAgent.#',  # do not subscribe to toAgent else we will have duplication in GUI
]

UI_REPLY_TOPICS = [
    'ui.user.1.reply',
    'ui.user.2.reply',
    'ui.user.all.reply',
]


# TODO import this from event bus utils once we have sth stable regarding threaded uses of connections
def publish_message(connection, message):
    """
    Publishes message into the correct topic (uses Message object metadata)
    Creates temporary channel on it's own
    Connection must be a pika.BlockingConnection
    """
    channel = None

    logger.debug('publishing..')
    properties = pika.BasicProperties(**message.get_properties())

    try:
        channel = connection.channel()
        channel.basic_publish(
            exchange=AMQP_EXCHANGE,
            routing_key=message.routing_key,
            properties=properties,
            body=message.to_json(),
        )

    except (pika.exceptions.ConnectionClosed, BrokenPipeError):

        print("Log handler connection closed. Reconnecting..")

        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))  # this doesnt overwrite connection argument!
        channel = connection.channel()

        # send retry
        channel.basic_publish(
            exchange=AMQP_EXCHANGE,
            routing_key=message.routing_key,
            properties=properties,
            body=message.to_json(),
        )

    finally:
        if channel and channel.is_open:
            channel.close()


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


mapping_testsuite_to_message_translator = {
    'dummy': DummySessionMessageTranslator,
    'coap': CoAPSessionMessageTranslator,
    'onem2m': OneM2MSessionMessageTranslator,
    '6lowpan': SixLoWPANSessionMessageTranslator,
    'comi': CoMISessionMessageTranslator
}

DEFAULT_NODE_TO_USER_MAPPING = {
    'coap_client': '1',
    'coap_server': '2',
}

# see doc from GenericBidirectonalTranslator.__doc__
queue_messages_display_to_ui = Queue(maxsize=100)
queue_messages_request_to_ui = Queue(maxsize=100)
queue_messages_from_tt = Queue(maxsize=100)
queue_messages_from_ui = Queue(maxsize=100)
queue_messages_to_tt = Queue(maxsize=100)

queues = [
    queue_messages_to_tt,
    queue_messages_display_to_ui,
    queue_messages_request_to_ui,
    queue_messages_from_tt,
    queue_messages_from_ui
]


class AmqpMessagePublisher:
    DEFAULT_EXCHAGE = 'amq.topic'
    DEFAULT_AMQP_URL = 'amqp://guest:guest@locahost/'

    def __init__(self, amqp_url, amqp_exchange):

        self.COMPONENT_ID = 'amqp_publisher_%s' % str(uuid.uuid4())[:8]

        self.connection = None
        self.channel = None

        if amqp_exchange:
            self.exchange = amqp_exchange
        else:
            self.exchange = self.DEFAULT_EXCHAGE

        if amqp_url:
            self.amqp_url = amqp_url
        else:
            self.amqp_url = self.DEFAULT_AMQP_URL

        self.amqp_connect()

    def amqp_connect(self):
        self.connection = pika.BlockingConnection(pika.URLParameters(self.amqp_url))
        self.channel = self.connection.channel()

        # Hello world message
        m = MsgTestingToolComponentReady(
            component=self.COMPONENT_ID,
            description="%s is READY" % self.COMPONENT_ID

        )

        self.channel.basic_publish(
            body=m.to_json(),
            routing_key=m.routing_key,
            exchange=self.exchange,
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )

    def stop(self):

        if self.channel:
            self.channel.close()
            self.channel = None

        if self.connection:
            self.connection.close()
            self.connection = None

    def publish_ui_display(self, message: Message, user_id=None, level=None):

        # TODO fix this
        user_id = 'all'

        # set message route
        if user_id:
            message.routing_key = "ui.user.%s.display" % user_id
        elif hasattr(message, "node"):
            message.routing_key = "ui.user.%s.display" % DEFAULT_NODE_TO_USER_MAPPING['node']
        else:
            raise Exception('Not enough information to know where to route message')

        publish_message(self.connection, message)

        logger.info(
            "publishing: %s routing_key: %s" % (repr(message)[:STDOUT_MAX_STRING_LENGTH], message.routing_key))

    def publish_message(self, message):
        """
        Generic publish message which uses class connection

        :param message:
        :return:
        """
        publish_message(self.connection, message)

        logger.info("publishing:%s routing_key: %s correlation_id %s"
                    % (repr(message)[:STDOUT_MAX_STRING_LENGTH],
                       message.routing_key,
                       message.correlation_id if hasattr(message, 'correlation_id') else None))

    def publish_ui_request(self, message, user_id=None):
        """
        :param message:
        :param request_name: Typically the field name of the button/file/etc
        :param user_id:
        :return:
        """
        # TODO fix this
        user_id = 'all'

        # set message route
        if user_id:
            message.routing_key = "ui.user.%s.request" % user_id
            message.reply_to = "ui.user.%s.reply" % user_id
        elif hasattr(message, "node"):
            message.routing_key = "ui.user.%s.request" % DEFAULT_NODE_TO_USER_MAPPING['node']
            message.reply_to = "ui.user.%s.reply" % DEFAULT_NODE_TO_USER_MAPPING['node']
        else:
            raise Exception('Not enough information to know where to route message')

        self.publish_message(message)

    def publish_tt_chained_message(self, message):
        """
        This is a dummy publisher, all the required treatment has already been done by translation functions
        """
        publish_message(self.connection, message)

        logger.info("publishing:%s routing_key: %s correlation_id %s"
                    % (repr(message)[:STDOUT_MAX_STRING_LENGTH],
                       message.routing_key,
                       message.correlation_id if hasattr(message, 'correlation_id') else None))

    def synch_request(self, request, timeout=30):
        """
        :param message: request Message
        :param timeout: Timeout in seconds, else expection is raised
        :return: Reply message
        """
        return amqp_request(self.connection, request, COMPONENT_ID, retries=timeout * 2)


def main():
    logger.info('Using params: AMQP_URL=%s | AMQP_EXCHANGE=%s' % (AMQP_URL, AMQP_EXCHANGE))

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "test_suite",
            help="Test suite name",
            choices=list(mapping_testsuite_to_message_translator.keys())
        )

        args = parser.parse_args()

    except Exception as e:
        logger.error(e)
        return

    try:
        message_translator = mapping_testsuite_to_message_translator[args.test_suite]()
    except KeyError:
        logger.error("Error launching test suite: %s" % args.test_suite)
        return

    # auxiliary functions

    def process_message_from_ui(message_received):
        logger.info("routing TT <- UI: %s | r_key: %s | corr_id %s"
                    % (repr(message_received)[:STDOUT_MAX_STRING_LENGTH],
                       message_received.routing_key,
                       message_received.correlation_id if hasattr(message_received, 'correlation_id') else None))

        # 0. print pending responses table
        message_translator.print_table_of_pending_messages()

        # 1. echo user's response to every user in session
        text_message = 'User replied to request: %s' % repr(message_received.fields)
        message = message_translator.transform_string_to_ui_markdown_display(text_message)
        queue_messages_display_to_ui.put(message)

        # 2. Handle reply from user
        if message_translator.is_pending_response(message_received):
            logger.info('got reply to previous request, r_key: %s corr id %s, message %s'
                        % (
                            message_received.routing_key,
                            message_received.correlation_id if hasattr(message_received, 'correlation_id') else None,
                            repr(message_received),
                        ))

            response_to_tt = message_translator.translate_ui_to_tt_message(message_received)

            # 3. Some replies are just confirmations , no chained TT actions associated to them
            if response_to_tt is None:
                return

            logger.info("publishing:%s routing_key: %s"
                        % (repr(response_to_tt)[:STDOUT_MAX_STRING_LENGTH],
                           response_to_tt.routing_key))

            # 4. we have a chained response for the TT
            queue_messages_to_tt.put(response_to_tt)

        else:
            logger.info("Not in responses pending list. Duplication? Two users replied to same request?")

    def process_message_from_testing_tool(message_received):
        logger.info("routing TT -> UI: %s | r_key: %s | corr_id %s"
                    % (repr(message_received)[:STDOUT_MAX_STRING_LENGTH],
                       message_received.routing_key,
                       message_received.correlation_id if hasattr(message_received, 'correlation_id') else None))

        # 0. update message factory states
        message_translator.update_state(message_received)

        # 1. echo message to user (if applicable)
        if type(message_received) not in MESSAGES_NOT_TO_BE_ECHOED:
            ui_display_message = message_translator.transform_message_to_ui_markdown_display(message_received)
            if ui_display_message:
                queue_messages_display_to_ui.put(ui_display_message)

        # 2. request input from user (if applicable)
        ui_request_message = message_translator.get_ui_request_action_message(message_received)
        if ui_request_message:
            ui_request_message = message_translator.tag_message(ui_request_message)
            queue_messages_request_to_ui.put(ui_request_message)

    # start of UI adaptor flow control
    amqp_message_publisher = AmqpMessagePublisher(
        amqp_url=AMQP_URL,
        amqp_exchange=AMQP_EXCHANGE)

    # we need to queuing all TT messsages from begining of session
    tt_amqp_listener_thread = AmqpListener(
        amqp_url=AMQP_URL,
        amqp_exchange=AMQP_EXCHANGE,
        topics=TESTING_TOOL_TOPIC_SUBSCRIPTIONS,
        callback=queue_messages_from_tt.put)

    tt_amqp_listener_thread.setName('TT_listener_thread')
    tt_amqp_listener_thread.start()

    logger.info("UI adaptor bootstrapping..")
    # .bootstrap(producer) call blocks until it has done its thing (got users info, session configs were retireved,etc)
    message_translator.bootstrap(amqp_message_publisher)

    logger.info("UI adaptor entering test suite execution phase..")

    ui_amqp_listener_thread = AmqpListener(
        amqp_url=AMQP_URL,
        amqp_exchange=AMQP_EXCHANGE,
        topics=UI_REPLY_TOPICS,
        callback=queue_messages_from_ui.put)

    ui_amqp_listener_thread.setName('UI_listener_thread')
    ui_amqp_listener_thread.start()
    logger.info("UI adaptor is up and listening on the bus ..")

    # this loop processes all incoming messages and dispatches them to its corresponding handler
    loop_count = 0
    try:
        while True:

            # get next message from TT
            if not queue_messages_from_tt.empty():
                msg_from_tt = queue_messages_from_tt.get()
                process_message_from_testing_tool(msg_from_tt)  # this populates the *_to_ui queues

            # publish all pending display messages to UIs
            while not queue_messages_display_to_ui.empty():
                msg_ui_to_display = queue_messages_display_to_ui.get()
                amqp_message_publisher.publish_ui_display(msg_ui_to_display)

            # get and publish next request for UI (just one at a time)
            # TODO implement a mechanism for not publish messages until previous one has been replied,
            # how to handle the ui.user.request cancel command tho?

            if not queue_messages_request_to_ui.empty():
                # get next request
                request = queue_messages_request_to_ui.get()
                # publish it
                amqp_message_publisher.publish_ui_request(request)
                # prepare the entry for still-pending-responses table
                requested_fields = message_translator.get_field_keys_from_ui_request(request)
                message_translator.add_pending_response(
                    corr_id=request.correlation_id,
                    request_message=request,
                    requested_field_name_list=requested_fields,
                )

            # get next message reply from UI
            if not queue_messages_from_ui.empty():
                process_message_from_ui(queue_messages_from_ui.get())  # this populates the *_to_tt queue

            # publish all pending messages to TT (there shouldn't not be more than one at a time)
            while not queue_messages_to_tt.empty():
                message_translator.print_table_of_pending_messages()
                msg_to_tt = queue_messages_to_tt.get()
                amqp_message_publisher.publish_tt_chained_message(msg_to_tt)

            if loop_count == 1000:
                for q in queues:
                    logger.debug("queue %s size: %s" % (repr(q), q.qsize()))
                loop_count = 0
                logger.debug("reset loop count")
            else:
                loop_count += 1

            time.sleep(0.01)

    except KeyboardInterrupt:
        logger.info('user interruption captured, exiting..')

    finally:

        logger.info('UI adaptor stopping..')
        amqp_message_publisher.stop()  # not a thread
        tt_amqp_listener_thread.stop()  # thread
        ui_amqp_listener_thread.stop()  # thread
        tt_amqp_listener_thread.join()
        ui_amqp_listener_thread.join()


if __name__ == '__main__':
    main()
