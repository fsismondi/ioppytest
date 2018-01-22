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

# TODO synthesise imports in __all__
from ioppytest.finterop_ui_adaptor import (UiResponseError,
                                           COMPONENT_ID,
                                           STDOUT_MAX_STRING_LENGTH,
                                           MESSAGES_NOT_TO_BE_ECHOED,
                                           TESTING_TOOL_TOPIC_SUBSCRIPTIONS,
                                           UI_REPLY_TOPICS)
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

mapping_testsuite_to_message_translator = {
    'dummy': DummySessionMessageTranslator,
    'coap': CoAPSessionMessageTranslator,
    'onem2m': OneM2MSessionMessageTranslator,
    '6lowpan': SixLoWPANSessionMessageTranslator,
    'comi': CoMISessionMessageTranslator
}

# see doc from GenericBidirectonalTranslator.__doc__
queue_messages_display_to_ui = Queue(maxsize=10)
queue_messages_request_to_ui = Queue(maxsize=10)
queue_messages_from_tt = Queue(maxsize=10)
queue_messages_from_ui = Queue(maxsize=10)
queue_messages_to_tt = Queue(maxsize=10)

queues = [
    queue_messages_to_tt,
    queue_messages_display_to_ui,
    queue_messages_request_to_ui,
    queue_messages_from_tt,
    queue_messages_from_ui
]


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

class AmqpMessagePublisher:
    def __init__(self,
                 amqp_url='amqp://guest:guest@locahost/',
                 amqp_exchange='amq.topic',
                 iut_role_to_user_id_mapping=None):

        self.COMPONENT_ID = 'amqp_publisher_%s' % str(uuid.uuid4())[:8]

        if iut_role_to_user_id_mapping:
            self.iut_role_to_user_id_mapping = iut_role_to_user_id_mapping
        else:
            self.iut_role_to_user_id_mapping = dict()

        self.amqp_url = amqp_url
        self.exchange = amqp_exchange
        self.connection = None
        self.channel = None
        self.amqp_connect()

    def update_iut_role_to_user_id_mapping(self, iut_role_to_user_id_mapping):
        if iut_role_to_user_id_mapping:
            self.iut_role_to_user_id_mapping.update(iut_role_to_user_id_mapping)

    def get_user_id_from_node(self, node):
        """
        returns user_id or 'all' (in case we dont have any info about this)
        """
        try:
            return self.iut_role_to_user_id_mapping[node]
        except KeyError:
            return 'all'

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

        logger.info("publishing message DISPLAY for UI")

        # if user_id is not passed then let's introspect the message to see where to route it
        if user_id:
            pass
        elif hasattr(message, 'node'):
            user_id = self.get_user_id_from_node(message.node)
        else:
            user_id = 'all'

        message.routing_key = "ui.user.%s.display" % user_id

        self.publish_message(message)

    def publish_message(self, message):
        """
        Generic publish message which uses class connection
        Publishes message into the correct topic (uses Message object metadata)
        Creates temporary channel on it's own
        Connection must be a pika.BlockingConnection
        """
        channel = None
        properties = pika.BasicProperties(**message.get_properties())

        logger.info("publishing to routing_key: %s correlation_id %s, msg: %s"
                    % (message.routing_key,
                       message.correlation_id if hasattr(message, 'correlation_id') else None,
                       repr(message)[:STDOUT_MAX_STRING_LENGTH],))

        try:
            channel = self.connection.channel()
            channel.basic_publish(
                exchange=AMQP_EXCHANGE,
                routing_key=message.routing_key,
                properties=properties,
                body=message.to_json(),
            )

        except (pika.exceptions.ConnectionClosed, BrokenPipeError):

            print("Log handler connection closed. Reconnecting..")

            connection = pika.BlockingConnection(
                pika.URLParameters(AMQP_URL))  # this doesnt overwrite connection argument!
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

    def publish_ui_request(self, message, user_id=None):
        """
        :param message:
        :param request_name: Typically the field name of the button/file/etc
        :param user_id:
        :return:
        """

        # if user_id is not passed then let's introspect the message to see where to route it

        logger.info("publishing message REQUEST for UI")
        if user_id:
            pass
        elif hasattr(message, 'node'):
            user_id = self.get_user_id_from_node(message.node)
        else:
            user_id = 'all'

        message.routing_key = "ui.user.%s.request" % user_id
        message.reply_to = "ui.user.%s.reply" % user_id
        self.publish_message(message)

    def publish_tt_chained_message(self, message):
        """
        This is a dummy publisher, all the required treatment has already been done by translation functions
        """
        logger.info("publishing message for TT")
        self.publish_message(message)

    def synch_request(self, request, timeout=30):
        """
        :param message: request Message
        :param timeout: Timeout in seconds, else expection is raised
        :return: Reply message
        """
        return amqp_request(self.connection, request, COMPONENT_ID, retries=timeout * 2)


# auxiliary functions
def get_session_configuration_from_ui(amqp_publisher):
    resp = None
    session_configuration = None
    try:
        resp = amqp_publisher.synch_request(MsgUiRequestSessionConfiguration())
        if resp and resp.ok:
            # echo session config in UI
            m = MsgUiDisplay(fields=[
                {"type": "p",
                 "value": "Session config: \n%s" % json.dumps(resp.to_dict(), indent=4, sort_keys=True)},
            ])
            amqp_publisher.publish_ui_display(m)

            # set global
            session_configuration = resp.to_dict()

    except Exception:
        err_msg = "Error trying to get configuration from UI, got %s" % repr(resp)
        m = MsgUiDisplay(fields=[
            {"type": "p",
             "value": err_msg}
        ])
        logger.warning(err_msg)
        amqp_publisher.publish_ui_display(m)

    return session_configuration


def get_current_users_online(amqp_publisher):
    session_configuration = get_session_configuration_from_ui(amqp_publisher)
    return len(session_configuration['users'])


def get_user_ids_and_roles_from_ui(message_translator, amqp_publisher, session_configuration):
    shared_session = session_configuration and \
                     'shared' in session_configuration and \
                     session_configuration['shared'] is True
    expected_user_quantity = 2 if shared_session else 1

    if session_configuration and 'users' in session_configuration:
        iut_roles = message_translator.get_iut_roles()
        roles_to_user_mapping = {}
        #
        # do
        # something
        # here...

        while get_current_users_online(message_translator, amqp_publisher) < expected_user_quantity:
            info_msg = 'Waiting for at least 2 users to join the session..'
            amqp_publisher.publish_ui_display(info_msg)
            logger.warning(info_msg)
            time.sleep(5)
            resp = amqp_publisher.synch_request(MsgUiRequestSessionConfiguration())

        logger.warning("Both users connected: %s" % resp.users)

        for iut_role in iut_roles:
            # user 1 id
            m = MsgUiRequestTextInput(
                title="What's the user id driving %s? " % iut_role,
                fields=[
                    {
                        "type": "p",
                        "value": "you can get the user id by clicking in info button (top right of screen) -> "
                                 "'Users connected to the session'"
                    },
                    {
                        "name": "user_id",
                        "type": "text"
                    },
                    {
                        "name": "submit",
                        "type": "button",
                        "value": True
                    },
                    {
                        "name": " none ",
                        "type": "button",
                        "value": True
                    },

                ]
            )
            resp = amqp_publisher.synch_request(m)

            # echo reponse back to users
            m = MsgUiDisplay(fields=[
                {"type": "p",
                 "value": "Got : %s" % repr(resp)},
            ])
            amqp_publisher.publish_ui_display(m)

            logger.warning("||".join([str(type(resp)), str(type(resp.fields)), repr(resp)]))

            if resp.ok and 'user_id' in str(resp.fields):
                roles_to_user_mapping.update({iut_role, resp.fields['user_id']})
            elif resp.ok and 'none' in str(resp.fields):
                roles_to_user_mapping.update({iut_role, None})
            else:
                raise UiResponseError('received from the UI: %s' % repr(resp))

        else:
            logger.warning(
                "Cannot query users about roles with empty session configuration %s" % repr(session_configuration))

        logger.info("Roles to user mapping %s:" % roles_to_user_mapping)


def process_message_from_ui(message_translator, message_received):
    logger.info("routing TT <- UI: %s | r_key: %s | corr_id %s"
                % (repr(message_received)[:STDOUT_MAX_STRING_LENGTH],
                   message_received.routing_key,
                   message_received.correlation_id))

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
                        message_received.correlation_id,
                        repr(message_received),
                    ))

        response_to_tt = message_translator.translate_ui_to_tt_message(message_received)

        # 3. Some replies are just confirmations , no chained TT actions associated to them
        if response_to_tt is None:
            return

        # 4. we have a chained response for the TT
        queue_messages_to_tt.put(response_to_tt)

    else:
        logger.info("Not in responses pending list. Duplication? Two users replied to same request?")


def process_message_from_testing_tool(message_translator, message_received):
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


def main():
    # main vars
    iut_role_to_user_id_mapping = {}
    session_configuration = {}

    logger.info('Using params: AMQP_URL=%s | AMQP_EXCHANGE=%s' % (AMQP_URL, AMQP_EXCHANGE))

    # parse ARGS -> define which test suite we are executing

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "test_suite",
            help="Test suite name",
            choices=list(mapping_testsuite_to_message_translator.keys())
        )
        args = parser.parse_args()
        assert args.test_suite

    except Exception as e:
        logger.error(e)
        return

    try:
        # choose the message translator between CoAP, OneM2M, 6LoWPAN etc..
        message_translator = mapping_testsuite_to_message_translator[args.test_suite]()
    except KeyError:
        logger.error("Error launching test suite: %s" % args.test_suite)
        return

    amqp_message_publisher = AmqpMessagePublisher(
        amqp_url=AMQP_URL,
        amqp_exchange=AMQP_EXCHANGE,
        iut_role_to_user_id_mapping=None)

    # get config from UI
    session_configuration = get_session_configuration_from_ui(amqp_message_publisher)
    logger.info("Session configuration: %s" % repr(session_configuration))

    # this call is going to block until all users are present "in the room"
    iut_role_to_user_id_mapping = get_user_ids_and_roles_from_ui(amqp_message_publisher, message_translator,
                                                                 session_configuration)
    logger.info("IUTs roles to Users id mapping: %s" % repr(iut_role_to_user_id_mapping))

    # in case of user_to_user session AmqpMessagePublisher publishes to UI1 or UI2 or both, depending on what the
    # message that has been passed to publish() looks like, this is why amqp_message_publisher needs to be fed with
    # this mapping info
    amqp_message_publisher.update_iut_role_to_user_id_mapping(iut_role_to_user_id_mapping)

    # we need to start queuing all TT messages from beginning of session
    tt_amqp_listener_thread = AmqpListener(
        amqp_url=AMQP_URL,
        amqp_exchange=AMQP_EXCHANGE,
        topics=TESTING_TOOL_TOPIC_SUBSCRIPTIONS,
        callback=queue_messages_from_tt.put)

    tt_amqp_listener_thread.setName('TT_listener_thread')
    tt_amqp_listener_thread.start()

    logger.info("UI adaptor bootstrapping..")
    # bootstrap(producer) call blocks until it has done its thing
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
                process_message_from_testing_tool(message_translator, msg_from_tt)  # this populates the *_to_ui queues

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
                process_message_from_ui(message_translator,
                                        queue_messages_from_ui.get())  # this populates the *_to_tt queue

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
