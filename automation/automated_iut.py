# -*- coding: utf-8 -*-
# !/usr/bin/env python3

"""
AutomatedIUT class provides an interface for automated IUTs implementations using ioppytest environment.
See coap_client libcoap's automated_iut module for an example.
"""

import os
import platform
import signal
import socket
import subprocess
import sys
import threading

import pika
from event_bus_utils import publish_message
from event_bus_utils.rmq_handler import RabbitMQHandler, JsonFormatter
from messages import *

from ioppytest import AMQP_URL, AMQP_EXCHANGE, LOG_LEVEL

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
                                    timeout=timeout)
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
    implemented_testcases_list = NotImplementedField  # child MUST override
    component_id = NotImplementedField  # child MUST override
    implemented_stimuli_list = None  # child MAY override
    process_log_file = None  # child MAY override, log file will be dumped into python logger at the end of session

    def __init__(self, node):
        self._init_logger()

        assert self.implemented_testcases_list,  self.component_id

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

        self.log('Event received: %s' % type(event))

        if type(event) in self.event_to_handler_map:
            callback = self.event_to_handler_map[type(event)]
            callback(event)
        else:
            self.log('Event received and ignored: %s' % type(event))

    def handle_test_case_ready(self, event):
        if not self.implemented_testcases_list:  # either is None or []
            self.log('IUT didnt declare testcases capabilities, we assume that any can be run')
            return

        if event.testcase_id not in self.implemented_testcases_list:
            time.sleep(0.1)
            self.log('IUT %s (%s) CANNOT handle test case: %s' % (self.component_id, self.node, event.testcase_id))
            publish_message(self.connection, MsgTestCaseSkip(testcase_id=event.testcase_id))
        else:
            self.log('IUT %s (%s) READY to handle test case: %s' % (self.component_id, self.node, event.testcase_id))

    def handle_stimuli_execute(self, event):
        # TODO should we check if stimuli is implemented or not?
        if event.node == self.node and self.implemented_stimuli_list and event.step_id not in self.implemented_stimuli_list:
            self.log('[%s] STIMULI (%s) doesnt seem to be implemented by automated IUT:' %
                     (
                         self.node if self.node else "misc.",
                         event.step_id,
                     ))

        if event.node == self.node:
            step = event.step_id
            addr = event.target_address  # may be None
            try:
                self._execute_stimuli(step, addr)  # blocking till stimuli execution
                publish_message(self.connection, MsgStepStimuliExecuted(node=self.node))
            except NotImplementedError as e:  # either method not overriden, or stimuli step not implemented :/
                publish_message(self.connection, MsgStepStimuliExecuted(description=str(e), node=self.node))

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
        self.log('Got final test suite report')
        if self.process_log_file:
            contents = open(self.process_log_file, "r", encoding="utf-8").read()
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
