import os
import pika
import logging
import argparse
import threading

from ioppytest import AMQP_URL, AMQP_EXCHANGE
from ioppytest.utils.event_bus_utils import AmqpListener
from ioppytest.utils.rmq_handler import RabbitMQHandler, JsonFormatter
from ioppytest.utils.messages import *
from ioppytest.finterop_ui_adaptor import COMPONENT_ID, STDOUT_MAX_STRING_LENGTH, MESSAGES_NOT_TO_BE_ECHOED
from ioppytest.finterop_ui_adaptor.message_translators import (CoMISessionMessageTranslator,
                                                               CoAPSessionMessageTranslator,
                                                               SixLoWPANSessionMessageTranslator,
                                                               OneM2MSessionMessageTranslator,
                                                               GenericBidirectonalTranslator)
# init logging to stnd output and log files
logger = logging.getLogger("%s|%s" %(COMPONENT_ID,'amqp_connector'))
logger.setLevel(logging.DEBUG)

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)
#logger.setLevel(logging.INFO)

logging.getLogger('pika').setLevel(logging.WARNING)

TESTING_TOOL_TOPIC_SUBSCRIPTIONS = [
    MsgTestSuiteStart.routing_key,
    MsgTestingToolTerminate.routing_key,
    '#.fromAgent.#',
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

    logger.debug('[PUBLISHING] %s' % repr(connection))
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))  # this doesnt overwrite connection argument!
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


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


mapping_testsuite_to_message_translator = {
    'coap': CoAPSessionMessageTranslator,
    'onem2m': OneM2MSessionMessageTranslator,
    '6lowpan': SixLoWPANSessionMessageTranslator,
    'comi': CoMISessionMessageTranslator
}

DEFAULT_NODE_TO_USER_MAPPING = {
    'coap_client': '1',
    'coap_server': '2',
}


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
        print(e)

    try:
        message_translator = mapping_testsuite_to_message_translator[args.test_suite]()
    except KeyError:
        logger.error("Error launching test suite: %s" % args.test_suite)

    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    channel = connection.channel()

    lock = threading.RLock()

    def ui_display_producer(lock, message, user_id=None, level=None):

        with lock:
            # build Message object if passed attribute is string
            if type(message) is str:
                message = message_translator.transform_string_to_ui_markdown_display(message)

            assert isinstance(message, Message), "didnt Message pass verifications"

            # set message route
            if user_id:
                message.routing_key = "ui.user.%s.display" % user_id
            elif hasattr(message, "node"):
                message.routing_key = "ui.user.%s.display" % DEFAULT_NODE_TO_USER_MAPPING['node']
            else:
                raise Exception('Not enough information to know where to route message')

            publish_message(connection, message)

            logger.info(
                "publishing: %s routing_key: %s" % (repr(message)[:STDOUT_MAX_STRING_LENGTH], message.routing_key))

    def ui_request_producer(lock, message, user_id=None):
        """
        :param message:
        :param request_name: Typically the field name of the button/file/etc
        :param user_id:
        :return:
        """

        with lock:
            # set message route
            if user_id:
                message.routing_key = "ui.user.%s.request" % user_id
                message.reply_to = "ui.user.%s.reply" % user_id
            elif hasattr(message, "node"):
                message.routing_key = "ui.user.%s.request" % DEFAULT_NODE_TO_USER_MAPPING['node']
                message.reply_to = "ui.user.%s.reply" % DEFAULT_NODE_TO_USER_MAPPING['node']
            else:
                raise Exception('Not enough information to know where to route message')

            publish_message(connection, message)

            logger.info("publishing:%s routing_key: %s correlation_id %s"
                         % (repr(message)[:STDOUT_MAX_STRING_LENGTH],
                            message.routing_key,
                            message.correlation_id))

            message_translator.add_pending_response(
                corr_id=message.correlation_id,
                request_message=message,
                requested_field_name_list=GenericBidirectonalTranslator.get_field_keys_from_ui_request(message),
            )

    def on_message_received_from_ui(lock, message_received):
        with lock:
            logger.info("routing TT <- UI: %s | r_key: %s | corr_id %s"
                         % (repr(message_received)[:STDOUT_MAX_STRING_LENGTH],
                            message_received.routing_key,
                            message_received.correlation_id))

            # 0. print pending responses table
            message_translator.print_table_of_pending_messages()

            # 1. echo the some user's response to every user in session
            ui_display_producer(
                lock,
                message='User replied to request: %s' % repr(message_received.fields),
                level='debug',
                user_id='all'
            )

            # 2. Handle reply from user
            if message_translator.is_pending_response(message_received):

                logger.info('got reply to previous request, r_key: %s corr id %s, message %s'
                             % (
                                 message_received.routing_key,
                                 message_received.correlation_id,
                                 repr(message_received),
                             ))

                response_to_tt = message_translator.translate_ui_to_tt_message(message_received)

                # 3. Some replies are just confirmations , no chained TT actions associated to them
                if response_to_tt is None:
                    return

                logger.info("publishing:%s routing_key: %s"
                             % (repr(response_to_tt)[:STDOUT_MAX_STRING_LENGTH],
                                response_to_tt.routing_key))

                # 4. we have chained message for the TT
                publish_message(connection, response_to_tt)

            else:
                logger.info("Not in responses pending list. Duplication? Two users replied to same request?")

    def on_message_received_from_testing_tool(lock, message_received):
        with lock:
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
                    ui_display_producer(lock, ui_display_message, 'all')  # TODO handle routing

            # 2. request input from user (if applicable)
            ui_request_message = message_translator.get_ui_request_action_message(message_received)
            if ui_request_message:
                ui_request_message = message_translator.tag_message(ui_request_message)
                ui_request_producer(lock, ui_request_message, 'all')  # TODO handle routing

    def get_lock_and_dispatch_tt_message(message):
        with lock:
            logger.debug("LOCK acquired")
            on_message_received_from_testing_tool(lock, message)
        logger.debug("LOCK released")

    def get_lock_and_dispatch_ui_message(message):
        with lock:
            logger.debug("LOCK acquired")
            on_message_received_from_ui(lock, message)
        logger.debug("LOCK released")

    tt_amqp_listener_thread = AmqpListener(
        amqp_url=AMQP_URL,
        amqp_exchange=AMQP_EXCHANGE,
        topics=TESTING_TOOL_TOPIC_SUBSCRIPTIONS,
        callback=get_lock_and_dispatch_tt_message)

    ui_amqp_listener_thread = AmqpListener(
        amqp_url=AMQP_URL,
        amqp_exchange=AMQP_EXCHANGE,
        topics=UI_REPLY_TOPICS,
        callback=get_lock_and_dispatch_ui_message)

    tt_amqp_listener_thread.setName('TT_listener_thread')
    ui_amqp_listener_thread.setName('UI_listener_thread')

    tt_amqp_listener_thread.start()
    ui_amqp_listener_thread.start()

    logger.info('ui connector started listening to the event bus..')

    ui_request_producer(lock, message_translator.get_amqp_url_connection_message(), 'all')
    ui_display_producer(lock, message_translator.get_welcome_message(), 'all')

    tt_amqp_listener_thread.join()
    ui_amqp_listener_thread.join()

    logger.info('ui adaptor stopping..')


if __name__ == '__main__':
    main()
