# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import logging
import os

from transitions.core import MachineError
# TODO fix me! dont do agent stuff in coordinator
from ioppytest.agent.utils import bootstrap_agent
from ioppytest.utils.amqp_synch_call import *
from ioppytest import AMQP_EXCHANGE, AMQP_URL, LOG_LEVEL
from ioppytest import RESULTS_DIR
from ioppytest.utils.amqp_synch_call import publish_message, amqp_request
from ioppytest.utils.rmq_handler import RabbitMQHandler, JsonFormatter
from ioppytest.utils.exceptions import CoordinatorError
from ioppytest.utils.messages import *

# TODO these VARs need to come from the session orchestrator + test configuratio files
# TODO get filter from config of the TEDs
COAP_CLIENT_IUT_MODE = 'user-assisted'
COAP_SERVER_IUT_MODE = 'automated'
ANALYSIS_MODE = 'post_mortem'  # either step_by_step or post_mortem

# if left empty => packet_sniffer chooses the loopback
# TODO send flag to sniffer telling him to look for a tun interface instead!
SNIFFER_FILTER_IF = 'tun0'

# TODO 6lo FIX ME !
# - sniffer is handled in a complete different way (sniff amqp bus here! and not netwrosk interface using agent)
# - tun notify method -> execute only if test suite needs it (create a test suite param profiling)
# - COAP_CLIENT_IUT_MODE, COAP_SERVER_IUT_MODE , this should not exist in the code of the coord


# component identification & bus params
COMPONENT_ID = '%s|%s' % ('test_coordinator', 'amqp_connector')

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

TOUT_waiting_for_iut_configuration_executed = 5


class CoordinatorAmqpInterface(object):
    """
    This class listens to the event bus for test coordination services (like get testcases list etc..)
    and to test coordination events (like testcase start event etc..).
    """

    def __init__(self, amqp_url, amqp_exchange):

        self.amqp_url = amqp_url
        self.amqp_exchange = amqp_exchange

        self.amqp_connect()
        self.amqp_create_queues_bind_and_susbcribe()

        #  callbacks to coordinator methods (~services to other components)
        self.service_reponse_callbacks = {
            MsgTestSuiteGetTestCases: self.get_testcases_basic,
            MsgTestSuiteGetStatus: self.get_states_summary
        }

        # callbacks to state_machine transitions (see transitions table)
        self.control_events_triggers = {
            MsgSessionConfiguration: 'configure_testsuite',
            MsgConfigurationExecuted: 'iut_configuration_executed',
            MsgTestCaseStart: 'start_testcase',
            MsgStepStimuliExecuted: 'step_executed',
            MsgStepVerifyExecuted: 'step_executed',
            MsgStepCheckExecuted: 'step_executed',
            MsgTestCaseSelect: 'select_testcase',
            MsgTestSuiteStart: 'start_testsuite',
            MsgTestCaseSkip: 'skip_testcase',
        }

    def get_new_amqp_connection(self):
        return pika.BlockingConnection(pika.URLParameters(self.amqp_url))

    # def component_heart_beat(self):
    #     if self.connection and self.connection.is_open:
    #         publish_message(self.connection,MsgTest())

    def amqp_connect(self):
        self.connection = pika.BlockingConnection(pika.URLParameters(self.amqp_url))
        self.channel = self.connection.channel()
        self.channel.basic_qos(prefetch_count=1)

    def amqp_create_queues_bind_and_susbcribe(self):
        self.services_q_name = 'services@%s' % self.component_id
        self.events_q_name = 'events@%s' % self.component_id

        # declare services and events queues
        self.channel.queue_declare(queue=self.services_q_name, auto_delete=True)
        self.channel.queue_declare(queue=self.events_q_name, auto_delete=True)

        self.channel.queue_bind(exchange=self.amqp_exchange,
                                queue=self.services_q_name,
                                routing_key='control.testcoordination.service')

        self.channel.queue_bind(exchange=self.amqp_exchange,
                                queue=self.events_q_name,
                                routing_key='control.testcoordination')

        self.channel.queue_bind(exchange=self.amqp_exchange,
                                queue=self.events_q_name,
                                routing_key='control.session')

        self.channel.basic_consume(self.handle_service,
                                   queue=self.services_q_name,
                                   no_ack=False)

        self.channel.basic_consume(self.handle_control,
                                   queue=self.events_q_name,
                                   no_ack=False)

    def run(self):
        logger.info('starting to consume events from the bus..')

        # NOTE TO SELF, if blocking connections combined with start_consuming start
        # getting a lot of ConnectionResetByPeerErrors then implement our own loop
        # using pika.procese_events.thingy
        try:
            # while True:
            #     self.connection.process_data_events()
            #     self.component_heart_beat()
            #     self.connection.sleep(0.5)
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.channel.stop_consuming()

        # clean up
        self.channel.queue_delete(queue=self.services_q_name)
        self.channel.queue_delete(queue=self.events_q_name)
        self.channel.close()
        self.connection.close()

    def handle_service(self, ch, method, properties, body):

        # acknowledge message reception
        ch.basic_ack(delivery_tag=method.delivery_tag)

        props_dict = {
            'content_type': properties.content_type,
            'delivery_mode': properties.delivery_mode,
            'correlation_id': properties.correlation_id,
            'reply_to': properties.reply_to,
            'message_id': properties.message_id,
            'timestamp': properties.timestamp,
            'user_id': properties.user_id,
            'app_id': properties.app_id,
        }
        request = Message.from_json(body)
        request.update_properties(**props_dict)
        logger.info('Service request received: %s' % request._type)

        # let's process request
        if type(request) in self.service_reponse_callbacks:

            logger.info('Processing request: %s' % request._type)
            callback = self.service_reponse_callbacks[type(request)]

            try:
                response_data = callback()
                response = MsgReply(request, **response_data)
            except Exception as e:
                response = MsgReply(request,
                                    error_message=str(e),
                                    error_code='TBD')
                logger.error('[Coordination services error] %s' % e)

            publish_message(self.connection, response)
            return

        else:
            logger.debug('Ignoring service request: %s' % repr(request))

    def handle_control(self, ch, method, properties, body):

        # acknowledge message reception
        ch.basic_ack(delivery_tag=method.delivery_tag)

        props_dict = {
            'content_type': properties.content_type,
            'delivery_mode': properties.delivery_mode,
            'correlation_id': properties.correlation_id,
            'reply_to': properties.reply_to,
            'message_id': properties.message_id,
            'timestamp': properties.timestamp,
            'user_id': properties.user_id,
            'app_id': properties.app_id,
        }
        event = Message.from_json(body)
        event.update_properties(**props_dict)
        logger.info('Event received: %s' % event._type)

        # let's process request
        if type(event) in self.control_events_triggers:

            logger.info('Processing request: %s' % event._type)
            trigger_callback = self.control_events_triggers[type(event)]

            try:
                self.trigger(trigger_callback, event)  # dispatches event to FSM
                return

            except MachineError as fsm_err:
                logger.error('[Coordination FSM error] %s' % fsm_err)
                return

            except CoordinatorError as e:
                logger.error('[Coordination FSM error] %s' % e)
                return

        else:
            logger.debug('Ignoring event: %s' % repr(event))

    # # # FSM coordination publish/notify functions # # #

    def notify_testsuite_configured(self, received_event):
        event = MsgTestingToolConfigured(
            **self.testsuite.get_testsuite_configuration()
        )

        publish_message(self.get_new_amqp_connection(), event)

    def notify_testcase_finished(self, received_event):
        tc_info_dict = self.testsuite.get_current_testcase().to_dict(verbose=False)

        event = MsgTestCaseFinished(
            description='Testcase %s finished' % tc_info_dict['testcase_id'],
            **tc_info_dict
        )
        publish_message(self.get_new_amqp_connection(), event)

    def notify_testcase_verdict(self, received_event):
        tc_info_dict = self.testsuite.get_current_testcase().to_dict(verbose=False)
        tc_report = self.testsuite.get_testcase_report()

        msg_fields = {}
        msg_fields.update(tc_report)
        msg_fields.update(tc_info_dict)
        event = MsgTestCaseVerdict(**msg_fields)
        publish_message(self.get_new_amqp_connection(), event)

    def notify_testcase_ready(self, received_event):
        tc_info_dict = self.testsuite.get_current_testcase().to_dict(verbose=False)
        config_id = self.testsuite.get_current_testcase_configuration_id()
        config = self.testsuite.get_current_testcase_configuration().to_dict(verbose=True)

        msg_fields = {}
        msg_fields.update(tc_info_dict)
        msg_fields.update(config)
        msg_fields.update({'description': 'Next test case to be executed is %s' % tc_info_dict['testcase_id']})

        event = MsgTestCaseReady(
            **msg_fields
        )
        publish_message(self.get_new_amqp_connection(), event)

    def notify_step_execute(self, received_event):
        step_info_dict = self.testsuite.get_current_step().to_dict(verbose=True)
        tc_info_dict = self.testsuite.get_current_testcase().to_dict(verbose=False)
        config = self.testsuite.get_current_testcase_configuration().to_dict(verbose=True)
        config_id = self.testsuite.get_current_testcase_configuration_id()
        target_node = None
        try:
            target_node = self.testsuite.get_current_step_target_address()
        except Exception as e:
            logger.error(e)
            pass

        msg_fields = {}
        msg_fields.update(step_info_dict)  # put step info
        msg_fields.update(tc_info_dict)  # put tc info

        # if self.current_tc.current_step.iut: # put iut info
        #     msg_fields.update(self.current_tc.current_step.iut.to_dict())

        description_message = ['Please execute step: %s' % step_info_dict['step_id']]  # put some extra UI description
        description_message += ['Step description: %s' % step_info_dict['step_info']]

        if step_info_dict['step_type'] == "stimuli":
            # put target address info
            msg_fields.update({'target_address': target_node})

            # publish message
            event = MsgStepStimuliExecute(
                description=description_message,
                **msg_fields
            )

        elif step_info_dict['step_type'] == "verify":
            event = MsgStepVerifyExecute(
                description=description_message,
                **msg_fields
            )
        #
        elif step_info_dict['step_type'] == "check" or step_info_dict['step_type'] == "feature":
            logger.warning('CMD Step check or CMD step very not yet implemented')
            return  # not implemented

        publish_message(self.get_new_amqp_connection(), event)

    def notify_testcase_started(self, received_event):
        tc_info_dict = self.testsuite.get_current_testcase().to_dict(verbose=False)
        event = MsgTestCaseStarted(
            **tc_info_dict
        )
        publish_message(self.get_new_amqp_connection(), event)

    def notify_tun_interfaces_start(self, received_event):
        """
        Starts tun interface in user's agents agent TT.
        This is best effort approach, no exception is raised if the bootstrapping fails
        """
        logger.debug("Let's start the bootstrap the agents")

        # fixme desable this for tests that dont require TUNs
        nodes = self.testsuite.get_agents_addressing_from_configurations()

        for node_name, address_tuple in nodes.items():
            # convention -> agents are named the same as the node roles (coap_client, etc..)
            ipv6_network_prefix = address_tuple[0]
            ipv6_host = address_tuple[1]
            assigned_ip = ":%s" % ipv6_host

            bootstrap_agent.bootstrap(
                amqp_url=AMQP_URL,
                amqp_exchange=AMQP_EXCHANGE,
                agent_id=node_name,
                ipv6_host=assigned_ip,
                ipv6_prefix=ipv6_network_prefix,
                ipv6_no_forwarding=False
            )

    def notify_testsuite_ready(self, received_event):
        pass

    def notify_testsuite_started(self, received_event):
        event = MsgTestSuiteStarted(
        )
        publish_message(self.get_new_amqp_connection(), event)

    def notify_testsuite_finished(self, received_event):
        event = MsgTestSuiteReport(
            **self.testsuite.get_report()
        )
        publish_message(self.get_new_amqp_connection(), event)

    def notify_tescase_configuration(self, received_event):
        tc_info_dict = self.testsuite.get_current_testcase().to_dict(verbose=False)
        config_id = self.testsuite.get_current_testcase_configuration_id()
        config = self.testsuite.get_current_testcase_configuration().to_dict(verbose=True)

        for desc in config['description']:
            description = desc['message']
            node = desc['node']

            event = MsgConfigurationExecute(
                configuration_id=config_id,
                node=node,
                description=description,
                **tc_info_dict
            )
            publish_message(self.get_new_amqp_connection(), event)

            # TODO how new way of config for 6lo handling is implemented in the FSM?

    def notify_coordination_error(self, description, error_code):
        tc_info_dict = self.testsuite.get_current_testcase().to_dict(verbose=False)
        tc_id = self.testsuite.get_current_testcase_id()
        config_id = self.testsuite.get_current_testcase_configuration_id()
        config = self.testsuite.get_current_testcase_configuration().to_dict(verbose=True)

        # testcoordination.error notification
        # TODO error codes?
        coordinator_notif = OrderedDict()
        coordinator_notif.update({'description': description, })
        coordinator_notif.update({'error_code': error_code})
        # coordinator_notif.update({'testsuite_status': self.states_summary()})
        err_json = json.dumps(coordinator_notif)

        logger.error('Test coordination encountered critical error: %s' % err_json)
        if tc_id:
            filename = tc_id + '_error.json'
        else:
            filename = 'general_error.json'

        json_file = os.path.join(
            RESULTS_DIR,
            filename

        )
        with open(json_file, 'w') as f:
            f.write(err_json)

    # # # coordination synch calls (request/reply) # # #

    def call_service_sniffer_start(self, **kwargs):

        try:
            response = amqp_request(self.connection, MsgSniffingStart(**kwargs), COMPONENT_ID)
            logger.debug("Received answer from sniffer: %s, answer: %s" % (response._type, repr(response)))
            return response
        except AmqpSynchCallTimeoutError as e:
            logger.error("Sniffer API doesn't respond. Maybe it isn't up yet?")

    def call_service_sniffer_stop(self):

        try:
            response = amqp_request(self.connection, MsgSniffingStop(), COMPONENT_ID)
            logger.debug("Received answer from sniffer: %s, answer: %s" % (response._type, repr(response)))
            return response
        except AmqpSynchCallTimeoutError as e:
            logger.error("Sniffer API doesn't respond. Maybe it isn't up yet?")

    def call_service_sniffer_get_capture(self, **kwargs):

        try:
            response = amqp_request(self.connection, MsgSniffingGetCapture(**kwargs), COMPONENT_ID)
            logger.debug("Received answer from sniffer: %s, answer: %s" % (response._type, repr(response)))
            return response
        except AmqpSynchCallTimeoutError as e:
            logger.error("Sniffer API doesn't respond. Maybe it isn't up yet?")

    def call_service_testcase_analysis(self, **kwargs):

        request = MsgInteropTestCaseAnalyze(**kwargs)
        response = amqp_request(self.connection, request, COMPONENT_ID)
        logger.debug("Received answer from sniffer: %s, answer: %s" % (response._type, repr(response)))
        return response
