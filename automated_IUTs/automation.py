# -*- coding: utf-8 -*-
# !/usr/bin/env python3

"""
Example of python code for implementing an automated IUT.
AutomatedIUT class provides an interface for automated IUTs implementations.
"""

import os
import platform
import socket
import subprocess
import sys
import json
import pika
import signal
import logging
import threading

from messages import *
from event_bus_utils.rmq_handler import RabbitMQHandler, JsonFormatter
from event_bus_utils import publish_message
from ioppytest import AMQP_URL, AMQP_EXCHANGE, INTERACTIVE_SESSION, RESULTS_DIR, LOG_LEVEL

# timeout in seconds
STIMULI_HANDLER_TOUT = 15


@property
def NotImplementedField(self):
    raise NotImplementedError


def launch_long_automated_iut_process(cmd, process_logfile):
    """
    Launches IUT process and logs all output into file.
    This is NON BLOCKING.
    Doesnt return any value nor exception if process failed.
    """
    logging.info("Launching process with: %s" % cmd)
    logging.info('Process logging into %s' % process_logfile)
    with open(process_logfile, "w") as outfile:
        subprocess.Popen(cmd, stdout=outfile)  # subprocess.Popen does not block


def launch_short_automated_iut_process(cmd: list, timeout=STIMULI_HANDLER_TOUT):
    """
    Launches IUT process and logs all output using logger.
    Execution BLOCKS until process finished or exec time > STIMULI_HANDLER_TOUT

    Returns bool based of exec code, True if exec code is 0, else False
    """
    assert type(cmd) is list

    logging.info('IUT process cmd: {}'.format(cmd))
    try:
        o = subprocess.check_output(cmd,
                                    stderr=subprocess.STDOUT,
                                    shell=False,
                                    timeout=timeout,
                                    universal_newlines=True)
    except subprocess.CalledProcessError as p_err:
        logging.error('Stimuli failed (ret code: {})'.format(p_err.returncode))
        logging.error('Error: {}'.format(p_err))
        return False

    except subprocess.TimeoutExpired as tout_err:
        logging.error('Stimuli process executed but timed-out, probably no response from the server.')
        logging.error('Error: {}'.format(tout_err))
        return False

    logging.info('Stimuli ran successfully (ret code: {})'.format(str(o)))
    return True


def signal_int_handler(signal, frame):
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

    publish_message(
        connection,
        MsgTestingToolComponentShutdown(component='automated-iut')
    )

    logging.info('got SIGINT. Bye bye!')
    sys.exit(0)


signal.signal(signal.SIGINT, signal_int_handler)


class AutomatedIUT(threading.Thread):
    # attributes to be provided by subclass
    implemented_testcases_list = NotImplementedField  # child must override
    component_id = NotImplementedField  # child must override
    implemented_stimuli_list = None  # child may override
    process_log_file = None  # child may override, log file will be dumped into python logger at the end of session

    def __init__(self, node):
        self._init_logger()

        configuration = {}
        for i in ['implemented_testcases_list', 'component_id', 'node', 'process_log_file']:
            configuration[i] = getattr(self, i, "not defined")

        self.log("Initializing automated IUT: \n%s " % json.dumps(configuration, indent=4, sort_keys=True))

        threading.Thread.__init__(self)
        self.node = node
        self.event_to_handler_map = {
            MsgTestCaseReady: self.handle_test_case_ready,
            MsgStepVerifyExecute: self.handle_test_case_verify_execute,
            MsgStepStimuliExecute: self.handle_stimuli_execute,
            MsgTestSuiteReport: self.handle_test_suite_report,
            MsgTestingToolTerminate: self.handle_testing_tool_terminate,
            MsgConfigurationExecute: self.handle_configuration_execute,
            MsgAutomatedIutTestPing: self.handle_test_ping,
        }

        # lets setup the AMQP stuff
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

        self.message_count = 0

        # queues & default exchange declaration
        queue_name = '%s::eventbus_subscribed_messages' % "{comp}.{node}".format(
            comp=self.component_id,
            node=self.node
        )
        self.channel.queue_declare(queue=queue_name, auto_delete=True)

        for ev in self.event_to_handler_map:
            self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                    queue=queue_name,
                                    routing_key=ev.routing_key)
        # send hello message
        publish_message(
            self.connection,
            MsgTestingToolComponentReady(
                component="{comp}.{node}".format(
                    comp=self.component_id,
                    node=self.node
                )
            )
        )
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.on_request, queue=queue_name)

    def _init_logger(self):
        logger_id = self.component_id
        # init logging to stnd output and log files
        self._logger = logging.getLogger(logger_id)
        self._logger.setLevel(LOG_LEVEL)

        # add stream handler for echoing back into console
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        self._logger.addHandler(ch)

        # AMQP log handler with f-interop's json formatter
        rabbitmq_handler = RabbitMQHandler(AMQP_URL, logger_id)
        json_formatter = JsonFormatter()
        rabbitmq_handler.setFormatter(json_formatter)
        self._logger.addHandler(rabbitmq_handler)

    def log(self, message):
        """
        Class logger to be used by AutomatedIUT and children classes too.
        """
        self._logger.info(message)

        # # # #  INTERFACE to be overridden by child class # # # # # # # # # # # # # # # # # #

    def _exit(self):
        m = MsgTestingToolComponentShutdown(
            component="{comp}.{node}".format(
                comp=self.component_id,
                node=self.node
            )
        )
        publish_message(self.connection, m)
        time.sleep(2)
        self.connection.close()
        sys.exit(0)

    def _execute_verify(self, verify_step_id):
        """
        If IUT cannot perform verify validations then just override method with `pass` command

        :param verify_step_id:
        :return:
        """
        raise NotImplementedError("Subclasses should implement this!")

    def _execute_stimuli(self, stimuli_step_id, addr):
        """
        When executing IUT stimuli, the call MUST NOT block thread forever

        :param stimuli_step_id:
        :param addr:
        :return:
        """
        raise NotImplementedError("Subclasses should implement this!")

    # TODO fix me! no node should be passed, mabe pass config ID (test description defines one)
    def _execute_configuration(self, testcase_id, node):
        """
        If IUT doesnt need to configure anything then just override method with `pass` command

        :param testcase_id:
        :param node:
        :return:
        """
        raise NotImplementedError("Subclasses should implement this!")

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def run(self):
        self.log("Starting thread listening on the event bus")
        self.channel.start_consuming()
        self.log('Bye byes!')

    def stop(self):

        self.channel.stop_consuming()

    def on_request(self, ch, method, props, body):

        ch.basic_ack(delivery_tag=method.delivery_tag)

        event = Message.load_from_pika(method, props, body)

        self.message_count += 1

        if event is None:
            return

        self.log('Event received: %s' % repr(event))

        if type(event) in self.event_to_handler_map:
            callback = self.event_to_handler_map[type(event)]
            callback(event)
        else:
            self.log('Event received and ignored: %s' % type(event))

    def handle_test_case_ready(self, event):
        if self.implemented_testcases_list == []:
            self.log('IUT didnt declare testcases capabilities, we asume that any can be run')
            return

        if event.testcase_id not in self.implemented_testcases_list:
            time.sleep(0.1)
            self.log(
                'IUT %s (%s) pushing test case skip message for %s' % (self.component_id, self.node, event.testcase_id))
            publish_message(self.connection, MsgTestCaseSkip(testcase_id=event.testcase_id))
        else:
            self.log('IUT %s (%s) ready to execute testcase' % (self.component_id, self.node))

    def handle_stimuli_execute(self, event):
        if event.node == self.node and event.step_id in self.implemented_stimuli_list:
            step = event.step_id
            addr = event.target_address  # may be None
            self._execute_stimuli(step, addr)  # blocking till stimuli execution
            publish_message(self.connection, MsgStepStimuliExecuted(node=self.node))
        else:
            self.log('[%s] Event received and ignored: \n\tEVENT:%s \n\tNODE:%s \n\tSTEP: %s' %
                     (
                         self.node if self.node else "misc.",
                         type(event),
                         event.node,
                         event.step_id,
                     ))

    def handle_test_case_verify_execute(self, event):
        if event.node == self.node:
            step = event.step_id
            self._execute_verify(step)
            publish_message(self.connection,
                            MsgStepVerifyExecuted(verify_response=True,
                                                  node=self.node
                                                  ))
        else:
            self.log('Event received and ignored: %s (node: %s - step: %s)' %
                     (
                         type(event),
                         event.node,
                         event.step_id,
                     ))

    def handle_test_suite_report(self, event):
        self.log('Got final test suite report: %s' % event.to_json())
        if self.process_log_file:
            contents = open(self.process_log_file).read()
            self.log('*' * 72)
            self.log('AUTOMATED_IUT LOGS %s' % self.process_log_file)
            self.log('*' * 72)
            self.log(contents)
            self.log('*' * 72)
            self.log('*' * 72)

    def handle_testing_tool_terminate(self, event):
        self.log('Test terminate signal received. Quitting..')
        time.sleep(2)
        self._exit()

    def handle_configuration_execute(self, event):
        if event.node == self.node:
            self.log('Configure test case %s' % event.testcase_id)
            # TODO fix me _execute_config should pass an arbitrary dict, which
            # will be used later for building the fields of the ret message
            ipaddr = self._execute_configuration(event.testcase_id,
                                                 event.node)  # blocking till complete config execution
            if ipaddr != '':
                m = MsgConfigurationExecuted(testcase_id=event.testcase_id, node=event.node, ipv6_address=ipaddr)
                publish_message(self.connection, m)
        else:
            self.log('Event received and ignored: %s' % type(event))

    def handle_test_ping(self, event):
        if event.node == self.node:
            self.log('Testing L3 reachability.')
            reachable = AutomatedIUT.test_l3_reachability(event.target_address)

            if reachable:
                success = True
                msg = "Ping reply received, peer is reachable"
            else:
                success = False
                msg = "Ping reply not received, peer is unreachable"

            m = MsgAutomatedIutTestPingReply(
                # request=event.request,
                ok=success,
                description=msg,
                node=event.node,
                target_address=event.target_address
            )

            publish_message(self.connection, m)
            self.log('Event pushed: %s' % m)

    @classmethod
    def test_l3_reachability(cls, ip_address) -> bool:
        """
        Check if the peer (e.g another AutomatedIUT) designed by the given
        ip address is reachable at network layer.
        """
        opt_switch = 'n' if platform.system().lower() == "windows" else 'c'

        cmd = "ping -W {timeout} -{switch} 2 {ip}".format(timeout=2, switch=opt_switch,
                                                          ip=ip_address)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, shell=True)
        proc.wait(timeout=5)
        if proc.returncode == 0:
            logging.info('Ping test sucessful for {}'.format(ip_address))
            return True
        else:
            logging.info('Ping failed for {}'.format(ip_address))
            output = 'output = Process stderr:\n'
            while proc.poll() is None:
                output += str(proc.stderr.readline())
            output += str(proc.stderr.read())
            logging.info(output)
            return False

    @classmethod
    def test_l4_reachability(cls, ip_address, port) -> bool:
        """
        Check if the host designed by the given ip address listen and
        accept connection to the given port.
        This test must be only called from the client automated IUT to
        check if the server is running an implementation of the desired
        protocol
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            s.connect((ip_address, port))
            logging.info('Ip address {} is listening on port {}'
                         .format(ip_address, port))
            s.close()
            return True
        except ConnectionRefusedError:
            logging.info('Ip address {} refused connection on port {}'
                         .format(ip_address, port))
            s.close()
            return False


class UserMock(threading.Thread):
    """
    this class servers for moking user inputs into GUI
    """
    component_id = 'user_mock'

    # e.g. for TD COAP CORE from 1 to 31
    DEFAULT_TC_LIST = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 31)]

    def __init__(self, iut_testcases=None):

        self._init_logger()

        threading.Thread.__init__(self)

        self.event_to_handler_map = {
            MsgTestCaseReady: self.handle_test_case_ready,
            MsgTestingToolReady: self.handle_testing_tool_ready,
            MsgTestingToolConfigured: self.handle_testing_tool_configured,
            MsgTestSuiteReport: self.handle_test_suite_report,
            MsgTestCaseVerdict: self.handle_test_case_verdict,
            MsgTestingToolTerminate: self.handle_testing_tool_terminate,
        }

        self.shutdown = False
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

        self.message_count = 0
        # queues & default exchange declaration

        if iut_testcases:
            self.implemented_testcases_list = iut_testcases
        else:
            self.implemented_testcases_list = UserMock.DEFAULT_TC_LIST

        queue_name = '%s::eventbus_subscribed_messages' % self.component_id
        self.channel.queue_declare(queue=queue_name, auto_delete=True)

        for ev in self.event_to_handler_map:
            self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                    queue=queue_name,
                                    routing_key=ev.routing_key)

        publish_message(self.connection, MsgTestingToolComponentReady(component=self.component_id))
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.on_request, queue=queue_name)

    def _init_logger(self):
        logger_id = self.component_id
        # init logging to stnd output and log files
        self._logger = logging.getLogger(logger_id)
        self._logger.setLevel(LOG_LEVEL)

        # add stream handler for echoing back into console
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        self._logger.addHandler(ch)

        # AMQP log handler with f-interop's json formatter
        rabbitmq_handler = RabbitMQHandler(AMQP_URL, logger_id)
        json_formatter = JsonFormatter()
        rabbitmq_handler.setFormatter(json_formatter)
        self._logger.addHandler(rabbitmq_handler)

    def log(self, message):
        self._logger.info(message)

    def on_request(self, ch, method, props, body):

        ch.basic_ack(delivery_tag=method.delivery_tag)
        event = Message.load_from_pika(method, props, body)
        self.message_count += 1

        if type(event) in self.event_to_handler_map:
            callback = self.event_to_handler_map[type(event)]
            callback(event)
        else:
            if hasattr(event, 'description'):
                logging.info('Event received and ignored: < %s >  %s' % (type(event), event.description))
            else:
                logging.info('Event received and ignored: %s' % type(event))

    def handle_testing_tool_configured(self, event):
        m = MsgTestSuiteStart()
        publish_message(self.connection, m)
        logging.info('Event received: %s' % type(event))
        logging.info('Event description: %s' % event.description)
        logging.info('Event pushed: %s' % m)

    def handle_testing_tool_ready(self, event):
        # m = MsgSessionConfiguration(
        #     configuration={
        #         "testsuite.testcases": [
        #             "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
        #             "http://doc.f-interop.eu/tests/TD_COAP_CORE_02",
        #             "http://doc.f-interop.eu/tests/TD_COAP_CORE_03",
        #         ]
        #     }
        # )  # from TC1 to TC3
        #
        # publish_message(self.connection, m)
        logging.info('Event received: %s' % type(event))
        # logging.info('Event pushed %s' % m)

    def handle_test_case_ready(self, event):
        logging.info('Event received: %s' % type(event))
        logging.info('Event description: %s' % event.description)

        # m = MsgTestCaseStart()
        # publish_message(self.connection, m)

        if event.testcase_id in self.implemented_testcases_list:
            m = MsgTestCaseStart()
            publish_message(self.connection, m)

            self.log('Event pushed: %s' % m)
        else:
            m = MsgTestCaseSkip(testcase_id=event.testcase_id)
            publish_message(self.connection, m)
            self.log('Event pushed: %s' % m)

    def handle_test_case_verdict(self, event):
        self.log('Event received: %s' % type(event))
        self.log('Event description: %s' % event.description)
        self.log('Got a verdict: %s , complete message: %s' % (event.verdict, repr(event)))

        #  Save verdict
        json_file = os.path.join(
            RESULTS_DIR,
            event.testcase_id + '_verdict.json'
        )
        with open(json_file, 'w') as f:
            f.write(event.to_json())

    def handle_test_suite_report(self, event):
        self.log('Got final report: %s' % event.to_json())

    def handle_testing_tool_terminate(self, event):
        self.log('Event received: %s' % type(event))
        self.log('Event description: %s' % event.description)
        self.log('Terminating execution.. ')
        self.stop()

    def stop(self):
        self.shutdown = True

        if not self.connection.is_open:
            self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        publish_message(self.connection,
                        MsgTestingToolComponentShutdown(component=self.component_id))

        if self.channel.is_open:
            self.channel.stop_consuming()

        self.connection.close()

    def run(self):
        while self.shutdown is False:
            self.connection.process_data_events()
            time.sleep(0.3)
        self.log('%s shutting down..' % self.component_id)


if __name__ == "__main__":
    ENV_NODE_NAME = str(os.environ['NODE_NAME'])
    dummy_auto_iut_class = type("DummyAutomatedIUT",
                                (AutomatedIUT,),
                                {
                                    'implemented_testcases_list': None,
                                    'implemented_stimuli_list': None,
                                    'component_id': 'dummy_automated_iut',
                                }
                                )
    logging.info("starting dummy automated IUT, with %s" % ENV_NODE_NAME)
    auto_iut = dummy_auto_iut_class(ENV_NODE_NAME)
    auto_iut.run()
    auto_iut.join()
    logging.info("exiting dummy automated IUT, with %s" % ENV_NODE_NAME)
