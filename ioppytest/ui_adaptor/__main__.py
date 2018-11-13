#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import pika
import logging
import argparse
import traceback

from queue import Queue

from ioppytest.ui_adaptor.ui_tasks import (wait_for_all_users_to_join_session,
                                           get_current_users_online,
                                           get_session_configuration_from_ui,
                                           get_user_ids_and_roles_from_ui,
                                           get_field_keys_from_ui_request,
                                           get_field_keys_from_ui_reply,
                                           get_field_value_from_ui_reply,
                                           list_to_str,
                                           )

from ioppytest.ui_adaptor.tt_tasks import (configure_testing_tool,
                                           wait_for_testing_tool_ready,
                                           send_default_testing_tool_configuration
                                           )

from ioppytest import AMQP_URL, AMQP_EXCHANGE, LOG_LEVEL, LOGGER_FORMAT
from event_bus_utils import AmqpListener, amqp_request, AmqpSynchCallTimeoutError
from event_bus_utils.rmq_handler import RabbitMQHandler, JsonFormatter
from messages import *

# TODO synthesise imports in __all__
from ioppytest.ui_adaptor import (UiResponseError,
                                  SessionError,
                                  COMPONENT_ID,
                                  STDOUT_MAX_TEXT_LENGTH_PER_LINE,
                                  MESSAGES_NOT_TO_BE_ECHOED,
                                  TESTING_TOOL_TOPIC_SUBSCRIPTIONS)

from ioppytest.ui_adaptor.message_translators import (
    DummySessionMessageTranslator,
    CoMISessionMessageTranslator,
    CoAPSessionMessageTranslator,
    SixLoWPANSessionMessageTranslator,
    OneM2MSessionMessageTranslator,
    LwM2MSessionMessageTranslator,
    WoTSessionMessageTranslator,
)

# init logging with stnd output and amqp handlers
logging.basicConfig(format=LOGGER_FORMAT)
logger = logging.getLogger("%s|%s" % (COMPONENT_ID, 'amqp_connector'))
logger.setLevel(LOG_LEVEL)

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)

logging.getLogger('pika').setLevel(logging.WARNING)

# timer used to avoid bumpping into UI error (message dropped on two "simultaneous" messages arrival )
PUBLISH_DELAY = 0.1

# globals
iut_role_to_user_id_mapping = {}
session_configuration = {}
online_users = []

mapping_testsuite_to_message_translator = {
    'dummy': DummySessionMessageTranslator,
    'coap': CoAPSessionMessageTranslator,
    'onem2m': OneM2MSessionMessageTranslator,
    '6lowpan': SixLoWPANSessionMessageTranslator,
    'comi': CoMISessionMessageTranslator,
    'lwm2m': LwM2MSessionMessageTranslator,
    'wot': WoTSessionMessageTranslator,
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


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

class AmqpMessagePublisher:
    def __init__(self,
                 amqp_url='amqp://guest:guest@locahost/',
                 amqp_exchange='amq.topic',
                 iut_role_to_user_id_mapping=None):

        self.COMPONENT_ID = 'UI_publisher%s' % str(uuid.uuid4())[:8]

        # init AMQP comms
        self.amqp_url = amqp_url
        self.exchange = amqp_exchange
        self.connection = None
        self.channel = None
        self.amqp_connect()

        # init role->user_ID map
        self.iut_role_to_user_id_mapping = dict()
        if iut_role_to_user_id_mapping:
            self.update_iut_role_to_user_id_mapping(iut_role_to_user_id_mapping)

    def update_iut_role_to_user_id_mapping(self, iut_role_to_user_id_mapping):

        if iut_role_to_user_id_mapping and type(iut_role_to_user_id_mapping) is dict:
            self.iut_role_to_user_id_mapping.update(iut_role_to_user_id_mapping)

        logger.info(
            "Updated role->user id map:\n%s" % json.dumps(self.iut_role_to_user_id_mapping, indent=4))

    def get_user_id_from_node(self, node):
        """
        returns user_id or 'all' (in case we dont have any info about this)
        """
        try:
            return self.iut_role_to_user_id_mapping[node]
        except KeyError:
            return 'all'

    def get_user_id_from_rkey(self, rkey):
        terms_list = rkey.split('.')
        if len(terms_list) == 4 and terms_list[0] == 'ui' and terms_list[1] == 'user':
            return terms_list[2]
        else:
            raise KeyError("Not a UI request/display routing key %s" % rkey)

    def get_session_users(self, exclude_user_id: str = None):
        """
        returns set of users, excluding exclude_user_id if passed as argument
        """
        ret = set(self.iut_role_to_user_id_mapping.values())
        if exclude_user_id and exclude_user_id in ret:
            ret.remove(exclude_user_id)

        return ret

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

    def _notify_component_shutdown(self):

        # FINISHING... let's send a goodbye message
        msg = MsgTestingToolComponentShutdown(
            component=self.COMPONENT_ID,
            description="%s is out!. Bye!" % self.COMPONENT_ID
        )
        self.publish_message(msg)

    def stop(self):

        self._notify_component_shutdown()

        if self.channel:
            self.channel.close()
            self.channel = None

        if self.connection:
            self.connection.close()
            self.connection = None

    def publish_ui_display(self, message: Message, user_id=None, level=None):

        if user_id:
            message = self._update_ui_message_rkeys(ui_message=message, user_id=user_id)

        if level:
            message.level = level

        logger.debug("Publishing message DISPLAY for UI: %s" % message.routing_key)
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

        logger.debug("Publishing to routing_key: %s, msg: %s"
                     % (message.routing_key,
                        repr(message)[:STDOUT_MAX_TEXT_LENGTH_PER_LINE],))

        try:
            time.sleep(PUBLISH_DELAY)
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

    def synch_request(self, request, user_id=None, timeout=30):
        """ method for synch requests:
        sends request, waits for response, and returns it (unless timeout, in that case it raises exception)
        :param message: request Message (any type of Message subclass object)
        :param timeout: Timeout in seconds, else exception is raised
        :return: MsgReply reply (MsgReply subclass object)
        """
        if user_id:
            request = self._update_ui_message_rkeys(ui_message=request, user_id=user_id)

        # if request to a user and is unicast (e.g. to user 1) then let's notify user2 that he's waiting for user1 reply
        if 'ui.user.' in request.routing_key and '.all.' not in request.routing_key:

            waiting_for_user = self.get_user_id_from_rkey(
                rkey=request.routing_key
            )

            assert waiting_for_user

            logger.debug("Publishing message REQUEST (synch call to {user}): {rk}".format(
                rk=request.routing_key,
                user=waiting_for_user
            ))

            # notify the other users that they will be waiting for another users request
            users = self.get_session_users(
                exclude_user_id=waiting_for_user
            )

            if not users:
                m = MsgUiDisplay(
                    fields=[{"type": "p", "value": "Waiting for {user} reply..".format(
                        user=waiting_for_user
                    )}]
                )

                self.publish_ui_display(
                    message=m,
                    user_id='all'
                )

            else:
                for u in users:
                    m = MsgUiDisplay(
                        fields=[{"type": "p", "value": "Waiting for {user} reply..".format(
                            user=waiting_for_user
                        )}]
                    )

                    self.publish_ui_display(
                        message=m,
                        user_id=u
                    )

        else:
            logger.debug("Publishing message REQUEST (synch call): {rk}".format(rk=request.routing_key, ))

        # fixme in amqp request use timeout instead of retries
        time.sleep(PUBLISH_DELAY)
        resp = amqp_request(self.connection,
                            request,
                            COMPONENT_ID,
                            retries=timeout * 2,
                            use_message_typing=True)
        return resp

    def publish_ui_request(self, request, user_id=None):
        """
        ASYNCHRONOUS UI request: sends message, and exits, Response needs to be consumed using the queuing system
        """

        if user_id:
            request = self._update_ui_message_rkeys(ui_message=request, user_id=user_id)

        # if request to a user and is unicast (e.g. to user 1) then let's notify user2 that he's waiting for user1 reply
        if 'ui.user.' in request.routing_key and '.all.' not in request.routing_key:

            waiting_for_user = self.get_user_id_from_rkey(
                rkey=request.routing_key
            )

            assert waiting_for_user

            logger.debug("Publishing message REQUEST (synch call to {user}): {rk}".format(
                rk=request.routing_key,
                user=waiting_for_user
            ))

            # notify the other users that they will be waiting for another users request
            users = self.get_session_users(
                exclude_user_id=waiting_for_user
            )

            if not users:
                logger.error("Got empty list of online users: %s " % users)
                m = MsgUiDisplay(
                    fields=[{"type": "p", "value": "Waiting for {user} reply..".format(
                        user=waiting_for_user
                    )}]
                )

                self.publish_ui_display(
                    message=m,
                    user_id='all'
                )

            else:
                for u in users:
                    m = MsgUiDisplay(
                        fields=[{"type": "p", "value": "Waiting for {user} reply..".format(
                            user=waiting_for_user
                        )}]
                    )

                    self.publish_ui_display(
                        message=m,
                        user_id=u
                    )

        else:
            logger.debug("Publishing message REQUEST (synch call): {rk}".format(
                rk=request.routing_key,
            ))

        self.publish_message(request)

    def publish_tt_chained_message(self, message):
        """
        This is a dummy publisher, all the required treatment has already been done by translation functions
        """
        logger.debug("Publishing message for TT: %s" % message.routing_key)
        self.publish_message(message)

    def _update_ui_message_rkeys(self, ui_message, tt_message=None, node_name=None, user_id=None):
        """ Updates UI messages routing key and reply to key.

        Behaviour:
        1. user_id (if passed as arg) is used for updating the destination UI
        2. node_name (if passed as arg) is used, combined with the roles_to_user mapping for updating the destination UI
        3. message destination is set to 'all' UI

        :return: ui_message with updated routing key and reply_to (when message is a request)
        """

        # FixMe: use data Messages typing instead of hasattribute(,) and " <.*.> in rkey" assertions
        destination_user = None

        if '.*.' in ui_message.routing_key or '.all.' in ui_message.routing_key:  # it's a user request/display
            if user_id:  # priority 1
                destination_user = user_id
            elif node_name:  # priority 2
                destination_user = self.get_user_id_from_node(node_name)
                if destination_user is None:
                    destination_user = 'all'
            elif tt_message and hasattr(tt_message, 'node'):  # priority 3
                destination_user = self.get_user_id_from_node(tt_message.node)
            else:
                destination_user = 'all'
        else:
            raise Exception("couldnt update the message UI destination in rkey")

        # lets set message rkey and reply_to fields
        if '*' in ui_message.routing_key:
            ui_message.routing_key = ui_message.routing_key.replace('*', destination_user)
            logger.debug("Routing to: %s" % destination_user)

            if hasattr(ui_message, 'reply_to'):
                ui_message.reply_to = ui_message.routing_key.replace('.request', '.reply')

        elif '.all.' in ui_message.routing_key:
            ui_message.routing_key = ui_message.routing_key.replace('.all.', '.{id}.'.format(id=destination_user))
            logger.debug("Routing to: %s" % destination_user)
            if hasattr(ui_message, 'reply_to'):
                ui_message.reply_to = ui_message.routing_key.replace('.request', '.reply')

        else:
            raise Exception('UI message passed??')

        return ui_message


def process_message_from_ui(message_translator, message_received):
    logger.info("routing TT <- UI: %s correlation_id %s, msg: %s"
                % (message_received.routing_key,
                   message_received.correlation_id if hasattr(message_received, 'correlation_id') else None,
                   repr(message_received)[:STDOUT_MAX_TEXT_LENGTH_PER_LINE],))

    # 0. print pending responses table
    message_translator.print_table_of_pending_responses()

    # 1. echo user's response to every user in session
    text_message = 'User replied to request: %s' % repr(list_to_str(message_received.fields))
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


def process_message_from_testing_tool(message_publisher, message_translator, message_received):
    logger.info("routing TT -> UI: %s correlation_id %s, msg: %s"
                % (message_received.routing_key,
                   message_received.correlation_id if hasattr(message_received, 'correlation_id') else None,
                   repr(message_received)[:STDOUT_MAX_TEXT_LENGTH_PER_LINE],))

    # 0. update message factory states
    message_translator.update_state(message_received)

    # 1. echo message to user (if applicable)
    if type(message_received) not in MESSAGES_NOT_TO_BE_ECHOED:
        ui_display_message = message_translator.translate_tt_to_ui_message(
            message=message_received)

        if ui_display_message:
            # fixme I shouldnt access _private method
            ui_display_message = message_publisher._update_ui_message_rkeys(
                ui_message=ui_display_message,
                tt_message=message_received)

            queue_messages_display_to_ui.put(ui_display_message)

    else:
        logger.info("routing TT -> UI: %s : message in DO_NOT_ECHO list" % (message_received.routing_key))

    # 2. request input from user (if applicable)
    ui_request_message = message_translator.get_ui_request_action_message(message_received)
    if ui_request_message:
        ui_request_message = message_translator.tag_message(ui_request_message)
        # fixme I should access _private method
        ui_request_message = message_publisher._update_ui_message_rkeys(
            ui_message=ui_request_message,
            tt_message=message_received)

        # add to requests queue
        queue_messages_request_to_ui.put(ui_request_message)

        # prepare the entry for still-pending-responses table
        requested_fields = get_field_keys_from_ui_request(ui_request_message)
        message_translator.add_pending_response(
            corr_id=ui_request_message.correlation_id,
            ui_request_message=ui_request_message,
            tt_request_originator=message_received,
            ui_requested_field_name_list=requested_fields,
        )

    else:
        logger.info("routing TT -> UI: %s : no associated action/request" % (message_received.routing_key))


def get_new_user_on_session(message_publisher):
    global online_users
    new_list_of_online_users = get_current_users_online(message_publisher)

    if len(new_list_of_online_users) > len(online_users):
        diff = list(set(new_list_of_online_users) - set(online_users))
        online_users = new_list_of_online_users
        return diff

    return None


def main():
    # main vars
    global iut_role_to_user_id_mapping
    global session_configuration
    global online_users

    logger.info('Using params: AMQP_URL=%s | AMQP_EXCHANGE=%s' % (AMQP_URL, AMQP_EXCHANGE))

    # ARGS define which test suite we are executing
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

    # we need to start queuing all TT messages from beginning of session
    amqp_message_publisher = AmqpMessagePublisher(
        amqp_url=AMQP_URL,
        amqp_exchange=AMQP_EXCHANGE,
        iut_role_to_user_id_mapping=None)

    tt_amqp_listener_thread = AmqpListener(
        amqp_url=AMQP_URL,
        amqp_exchange=AMQP_EXCHANGE,
        topics=TESTING_TOOL_TOPIC_SUBSCRIPTIONS,
        callback=queue_messages_from_tt.put)
    tt_amqp_listener_thread.setName('TT_listener_thread')
    tt_amqp_listener_thread.start()

    # # # # # # # # # # # # # # # # # #   GET SESSION INFO AND USER STUFF # # # # # # # # # # # # # # # # # # # # # # #

    # get config from UI
    session_configuration = get_session_configuration_from_ui(amqp_message_publisher)
    logger.info("Got session configuration reply from UI")

    # get list of all users which are online
    online_users = get_current_users_online(amqp_message_publisher)
    logger.info("Connected users: %s" % repr(online_users))

    # fixMe! WoT env introduced new requirements (several users per session, long lasting sessions )
    if args.test_suite != "wot":
        try:
            if "shared" in session_configuration and session_configuration["shared"]:
                logger.debug("session is SHARED")
            else:
                logger.debug("session is NOT SHARED (single-user vs automated-iut type)")

            # this call BLOCKS until all users are present "in the room"
            wait_for_all_users_to_join_session(message_translator,
                                               amqp_message_publisher,
                                               session_configuration)

            # create user_id -> iut_role mapping
            iut_role_to_user_id_mapping = get_user_ids_and_roles_from_ui(message_translator,
                                                                         amqp_message_publisher,
                                                                         session_configuration)

            logger.info("IUT_roles->users_id mapping: %s" % repr(iut_role_to_user_id_mapping))

            # In case of user_to_user session AmqpMessagePublisher publishes to UI1 or UI2 or both depending on what the
            # message that has been passed to publish() looks like.
            # Hence, amqp_message_publisher needs to be fed with the user->role mapping info
            amqp_message_publisher.update_iut_role_to_user_id_mapping(iut_role_to_user_id_mapping)

        except AmqpSynchCallTimeoutError as tout:
            err_msg = "UI response timeout, entering default testsuite configuration. \nException: %s" % str(tout)
            m = MsgUiDisplay(fields=[
                {"type": "p",
                 "value": err_msg}
            ])
            logger.error(err_msg)
            amqp_message_publisher.publish_ui_display(m, user_id='all', level='error')

        except UiResponseError as ui_error:
            err_msg = "UI response error caught. \nException: %s" % str(ui_error)
            m = MsgUiDisplay(fields=[
                {"type": "p",
                 "value": err_msg}
            ])
            logger.error(err_msg)
            # logger.error(traceback.format_exc())
            amqp_message_publisher.publish_ui_display(m, user_id='all', level='error')

        except SessionError as s_err:
            err_msg = "Session error caught. \nException: %s" % str(s_err)
            m = MsgUiDisplay(fields=[
                {"type": "p",
                 "value": err_msg}
            ])
            logger.error(s_err)
            logger.error(traceback.format_exc())
            amqp_message_publisher.publish_ui_display(m, user_id='all', level='error')
            return  # breaks the flow, user shoud restart the session if he want to give it another try

        except KeyboardInterrupt:
            logger.info('user interruption captured, exiting..')
            logger.info('UI adaptor stopping..')
            tt_amqp_listener_thread.stop()  # thread
            amqp_message_publisher.stop()  # not a thread
            return

        except Exception as err:
            logger.error(err)
            logger.error(traceback.format_exc())
            raise err

        # # # # # # # # # # # # # # # # # #  WAIT UNTIL TT IS READY # # # # # # # # # # # # # # # # # #

        try:
            wait_for_testing_tool_ready(amqp_message_publisher)
            logger.info("Configuring testing tool..")
            configure_testing_tool(amqp_message_publisher)

        except Exception as err:
            logger.error(err)
            logger.error(traceback.format_exc())
            send_default_testing_tool_configuration(amqp_message_publisher)

    # # # # # # # # # # # # # # # # #  SESSION EXECUTION  # # # # # # # # # # # # # # # # # #

    logger.info("UI adaptor bootstrapping..")

    # bootstrap(producer) call blocks until it has done its thing
    message_translator.bootstrap(amqp_message_publisher)

    logger.info("UI adaptor entering test suite execution phase..")

    # subscribe to UI replies
    ui_reply_topics = [
        'ui.user.all.reply',
    ]
    # for unicast channels (ui.user.<user_id>.reply)
    for k, v in iut_role_to_user_id_mapping.items():
        ui_reply_topics.append('ui.user.{user_id}.reply'.format(user_id=v))

    logger.info("UI responses subscriptions %s" % ui_reply_topics)
    ui_amqp_listener_thread = AmqpListener(
        amqp_url=AMQP_URL,
        amqp_exchange=AMQP_EXCHANGE,
        topics=ui_reply_topics,
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
                process_message_from_testing_tool(amqp_message_publisher, message_translator,
                                                  msg_from_tt)  # this populates the *_to_ui queues

            # publish all pending display messages to UIs
            while not queue_messages_display_to_ui.empty():
                msg_ui_to_display = queue_messages_display_to_ui.get()
                amqp_message_publisher.publish_ui_display(msg_ui_to_display)

            # get and publish next request for UI (just one at a time)
            if not queue_messages_request_to_ui.empty():
                # get next request
                request = queue_messages_request_to_ui.get()
                # send message to UI
                amqp_message_publisher.publish_ui_request(request)

            # get next message reply from UI
            if not queue_messages_from_ui.empty():
                process_message_from_ui(message_translator,
                                        queue_messages_from_ui.get())  # this populates the *_to_tt queue

            # publish all pending messages to TT (there shouldn't not be more than one at a time)
            while not queue_messages_to_tt.empty():
                message_translator.print_table_of_pending_responses()
                msg_to_tt = queue_messages_to_tt.get()
                amqp_message_publisher.publish_tt_chained_message(msg_to_tt)

            # this is for monitoring the consumed messages' queues
            if loop_count == 10001:
                for q in queues:
                    logger.debug("queue %s size: %s" % (repr(q), q.qsize()))
                loop_count = 0
                logger.debug("reset loop count")

            elif loop_count % 500 == 0:  # run less frequently
                new_users = get_new_user_on_session(amqp_message_publisher)
                if new_users:
                    logger.info("New users detected in the session. Calling handler")
                    message_translator.callback_on_new_users_in_the_session(amqp_message_publisher, new_users)

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
        logger.info('Starting UI adaptor..')
        # start main loop
        main()
        logger.info('Finishing UI adaptor..')

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
