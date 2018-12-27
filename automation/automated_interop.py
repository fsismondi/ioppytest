# -*- coding: utf-8 -*-
# !/usr/bin/env python3

"""
The automation code uses the event bus API as stimulation and evaluation point for driving and monitoring the tests.
Evaluates a normal test cycle with real automated IUTs.

This implmenets a python CLI for driving automated tests using ioppytest testing tools and automated IUTs.

Note: requires MAKE to be installed in the OS, and leverage from the Makefile in the root dir of the project.
For running very specif actions is recommended use make entry points (see Makefile) instead of this CLI.

usage: automated_interop.py [-h] [--all-interops] [--result-logger]
                            [--result-logger-only]

    optional arguments:
    -h, --help            show this help message and exit
    --all-interops        Runs all automated interop tests (requires local
                            docker daemon to be running, and tools to be already
                            build as docker images)
    --result-logger       Dumps all results into files
    --result-logger-only  Run (ONLY) a component to log all the results into
                            files

PRE-CONDITIONS:
- Export AMQP_URL in the running environment

TEST SETUP:

+-----------------------------------+                                       +--------------------------------+
|  +----------------------------+   |                                       | +----------------------------+ |
|  |       some CoAP client     |   |                                       | |      some CoAP server      | |
|  |        dockerizable        |   |                                       | |        dockerizable        | |
|  |      implementation        |   |                                       | |       implementaiton       | |
|  |      (e.g. libcoap)        |   |     +----------------------------+    | |      (e.g. californium)    | |
|  |                            |   |     |                            |    | |                            | |
|  +----------------------------+   |     |    interop testing tool    |    | +----------------------------+ |
|                                   |     |         ioppytest          |    |                                | 
|  +------tun interface--------+    |     |                            |    | +------tun interface--------+  | 
|                                   |     +----------------------------+    |            Agent (agent_y)     |
|                                   |                                       |                                |
| automated_iut-coap_client-libcoap |                ^    +                 | automated_iut-coap_server-californium 
|        docker container           |                |    |                 |        docker container        |
|                                   |                |    |                 |                                |
+-----------------------------------+                |    |                 +--------------------------------+
                                              events |    |  
            +     ^                                  |    |                            +     ^
            |     |                                  |    |                            |     |
            |     | events                           |    |                    events  |     | 
            |     |                                  |    |                            |     |
            v     +                                  +    v                            v     +

 +-------------------------------------------------------------------------------------------------------------------->
                                                AMQP Event Bus
<---------------------------------------------------------------------------------------------------------------------+
                                                     +     ^
                                                     |     |
                                                     |     | events
                                                     |     |
                                                     v     +
                                         +-----------------------------+
                                         |                             |
                                         |    automated interop driver |
                                         |        (this module)        |
                                         |                             |
                                         +-----------------------------+

"""

import os
import yaml
import pika
import pprint
import traceback
import argparse
import subprocess
import datetime

# messages and event_bus_utils are modules are installed with `pip3 install ioppytest-utils`
from automation import default_configuration, UIStub, ResultsLogToStdout
from event_bus_utils import publish_message, amqp_request, AmqpSynchCallTimeoutError

from messages import *
from ioppytest import AMQP_URL, AMQP_EXCHANGE, RESULTS_DIR
from ioppytest.ui_adaptor.message_rendering import testsuite_state_to_ascii_table
from automation import MessageLogger, log_all_received_messages, UserMock, ResultsLogToFile

COMPONENT_ID = 'perform_testsuite'
SESSION_TIMEOUT = 1200
EXECUTE_ALL_TESTS = os.environ.get('CI', 'False') == 'True'
LOG_WARNINGS_ONLY = os.environ.get('LOG_WARNINGS_ONLY', 'False') == 'True'
COAP_CLIENT_IS_AUTOMATED = os.environ.get('COAP_CLIENT_IS_AUTOMATED', 'True') == 'True'
COAP_SERVER_IS_AUTOMATED = os.environ.get('COAP_SERVER_IS_AUTOMATED', 'True') == 'True'

if LOG_WARNINGS_ONLY:
    logging.basicConfig(format='%(levelname)s [%(name)s]:%(message)s', level=logging.WARNING)
else:
    logging.basicConfig(format='%(levelname)s [%(name)s]:%(message)s', level=logging.INFO)
    logging.getLogger('pika').setLevel(logging.WARNING)
    logging.getLogger('event_bus_utils').setLevel(logging.WARNING)
    logging.getLogger('messages').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class PerformFullTest(object):
    """
    Automated interop test suite driver.

    Notes:
    This is pretty much independent from the protocol under test, unless using for doing integration tests.
    For that purpose run_all_tests_cases is leaved as None or False and EXECUTE_ALL_TESTS )imported from env is left
    undefined).
    I know.. ugly and confusing.. there are some legacy jenkins tests out there using this, so this avoids breaking that

    """

    def __init__(self,
                 run_all_tests_cases=None,
                 use_special_delimiters_for_report=True,
                 dump_results_to_files=False,
                 dump_files_directory=RESULTS_DIR):
        self.error_state = False
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

        if run_all_tests_cases or EXECUTE_ALL_TESTS:
            self.tc_list = None  # if tc_list is None => all TCs are executed
            logger.info("Full test suite execution mode detected. Executing all test cases.")
        else:
            logger.warning("Soon to be depricated! use run-all-tests-cases options instead!")
            self.tc_list = [
                'TD_COAP_CORE_01',
                'TD_COAP_CORE_02',
                'TD_COAP_CORE_03'
            ]  # the rest of the testcases are going to be skipped
            logger.info("Executing 3 first tests")

        self.non_automated_iuts = []

        if not COAP_CLIENT_IS_AUTOMATED:
            self.non_automated_iuts.append('coap_client')
        if not COAP_SERVER_IS_AUTOMATED:
            self.non_automated_iuts.append('coap_server')

        # prepare threads
        self.msg_logger_th = MessageLogger(AMQP_URL, AMQP_EXCHANGE)
        self.ui_services_stub_th = UIStub(AMQP_URL, AMQP_EXCHANGE)
        self.results_to_stdout_th = ResultsLogToStdout(AMQP_URL, AMQP_EXCHANGE, use_special_delimiters_for_report)
        self.u_mock_th = UserMock(iut_testcases=self.tc_list, iut_to_mock_verifications_for=self.non_automated_iuts)

        self.msg_logger_th.setName('msg_validator')
        self.u_mock_th.setName('user_mock_stub')
        self.ui_services_stub_th.setName('ui_services_stub')
        self.results_to_stdout_th.setName('results_to_stdout')

        self.threads = [
            self.u_mock_th,
            self.msg_logger_th,
            self.ui_services_stub_th,
            self.results_to_stdout_th,

        ]

        if dump_results_to_files:
            self.results_to_file_th = ResultsLogToFile(AMQP_URL, AMQP_EXCHANGE, results_dir=dump_files_directory)
            self.results_to_file_th.setName('results_to_file')
            self.threads.append(self.results_to_file_th)

        logger.info("Created threads: \n%s" % pprint.pformat(self.threads, indent=4))

    def stop(self):
        self.connection.close()

        if self.error_state:
            log_all_received_messages(self.msg_logger_th.messages_list)

    def run(self):

        try:
            for th in self.threads:
                th.start()

            self.check_session_start_status()

            logger.info("Sending session configuration to start tests")
            publish_message(
                self.connection,
                MsgSessionConfiguration(configuration=default_configuration),
            )  # configures test suite, this triggers start of userMock also

            t = 0
            # wait until we get MsgTestSuiteReport
            while t < SESSION_TIMEOUT and MsgTestSuiteReport not in self.msg_logger_th.messages_by_type_dict:
                time.sleep(5)
                t += 5

                if t % 15 == 0:
                    self.get_status()

            if t >= SESSION_TIMEOUT:
                r = amqp_request(self.connection,
                                 MsgTestSuiteGetStatus(),
                                 COMPONENT_ID)
                logger.warning('Test TIMED-OUT! Test suite status:\n%s' % pprint.pformat(r.to_dict()))
            else:
                assert MsgTestSuiteReport in self.msg_logger_th.messages_by_type_dict

                # we can now terminate the session
                publish_message(
                    self.connection,
                    MsgTestingToolTerminate(description="Received report, functional test finished..")
                )

                time.sleep(2)

        except Exception as e:
            self.error_state = True
            logger.error("Exception encountered in %s:\n%s" % (self.__class__.__name__, e))
            logger.error("Traceback:\n%s", traceback.format_exc())

        finally:
            if MsgTestingToolTerminate not in self.msg_logger_th.messages_by_type_dict:
                logger.warning('Never received TERMINATE signal')
                publish_message(
                    self.connection,
                    MsgTestingToolTerminate(description="Integration test of CoAP interop test: sth went wrong :/")
                )

            time.sleep(10)  # so threads process TERMINATE signal

            try:
                for th in self.threads:
                    if th.is_alive():
                        logger.warning("Thread %s didn't stop" % th.name)
                        th.stop()
            except Exception as e:  # i dont want this to make my tests fail
                logger.warning('Exception thrown while stopping threads:\n%s' % e)

    def check_session_start_status(self):
        retries_left = 10

        while retries_left > 0:
            try:
                current_status = amqp_request(
                    self.connection,
                    MsgTestSuiteGetStatus(),
                    COMPONENT_ID,
                    use_message_typing=True
                )  # get status
                if isinstance(current_status, MsgTestSuiteGetStatusReply):
                    for tc in current_status.tc_list:
                        if tc['state'] is not None:
                            raise Exception("Session has already (partly) run. Cannot perform full testsuite")

                    logger.debug("Session state seems to be ok to start")
                    return True
                else:
                    raise Exception("Unexpected reply when getting TestSuite status")
            except AmqpSynchCallTimeoutError as e:
                pass  # ignore it

            retries_left -= 1

        raise Exception("Unable to verify testsuite starting state")

    def get_status(self):
        try:
            current_status = amqp_request(
                self.connection,
                MsgTestSuiteGetStatus(),
                COMPONENT_ID,
                use_message_typing=True
            )  # get status

            if isinstance(current_status, MsgTestSuiteGetStatusReply):
                logger.info("Testsuite status: \n%s", testsuite_state_to_ascii_table(current_status.to_dict()))
            else:
                logger.warning("Could not get testsuite status: unexpected reply")
            pass
        except AmqpSynchCallTimeoutError as e:
            logger.warning("Could not get testsuite status: timeout")


# # # # # # AUXILIARY TEST METHODS # # # # # # #


def run_blocking_process(cmd: list, timeout=300):
    """
    Launches process and logs all output using logger.
    Execution BLOCKS until process finished or timed-out

    Returns bool based of exec code, True if exec code is 0, else False
    """
    assert type(cmd) is list

    logging.info('Process cmd: {}'.format(cmd))
    try:
        o = subprocess.check_output(cmd,
                                    stderr=subprocess.STDOUT,
                                    shell=False,
                                    timeout=timeout)
    except subprocess.CalledProcessError as p_err:
        logging.error('Execution failed, ret code: {}'.format(p_err.returncode))
        logging.error('Error: {}'.format(p_err))
        return False

    except subprocess.TimeoutExpired as tout_err:
        logging.error('Process executed but timed-out...')
        logging.error('Error: {}'.format(tout_err))
        return False

    # logging.info('Process ran successfully')
    return True


#######################


if __name__ == '__main__':
    MANIFEST_INTEROP_TESTS = 'automated_interop_tests.yaml'
    DELIM = "*" * 70

    # be careful with the order of the items as it's used along the main
    parser = argparse.ArgumentParser()

    parser.add_argument("--all-interops",
                        help="Runs all automated interop tests (requires local docker daemon to be running, "
                             "and tools to be already build as docker images)",
                        action="store_true")

    parser.add_argument("--result-logger",
                        help="Dumps all results into files",
                        action="store_true")

    parser.add_argument("--result-logger-only",
                        help="Run (ONLY) a component to log all the results into files",
                        action="store_true")

    args = parser.parse_args()

    if args.all_interops:
        logging.info("\n{delim}\nRUNNING ALL INTEROP SESSIONS COMBINATIONS\n{delim}".format(delim=DELIM))

        with open(MANIFEST_INTEROP_TESTS, 'r') as stream:
            manif = yaml.load(stream)

        for test in manif:
            logging.info('\n{delim} \n'
                         'Starting interop test session: \n'
                         '\tinterop test: {interop_name} \n'
                         '\tdatetime start: {datetime} \n'
                         '\tmake cmd: {cmd} \n'
                         '{delim}'.format(delim=DELIM,
                                          interop_name=test['name'],
                                          cmd=test['target_start'],
                                          datetime=datetime.datetime.now(),)
                         )

            # run make command
            run_blocking_process(['make', test['target_start']])

            # create dir for results
            test_dir = os.path.join(RESULTS_DIR, "{}_{}".format(str(datetime.datetime.now().date()), test['name']))
            os.makedirs(test_dir, exist_ok=True)

            # launch automated test driver
            pft = PerformFullTest(
                run_all_tests_cases=True,
                use_special_delimiters_for_report=False,
                dump_results_to_files=args.result_logger,
                dump_files_directory=test_dir,
            )
            pft.run()
            pft.stop()

            logging.info('\n{delim} \n'
                         'Stopping interop test session: \n'
                         '\tinterop test: {interop_name} \n'
                         '\tdatetime finished: {datetime} \n'
                         '\tmake cmd: {cmd} \n'
                         '{delim}'.format(delim=DELIM,
                                          interop_name=test['name'],
                                          cmd=test['target_stop'],
                                          datetime=datetime.datetime.now(),)
                         )

            run_blocking_process(['make', test['target_stop']])

    elif args.result_logger_only:
        results_to_file_th = ResultsLogToFile(AMQP_URL, AMQP_EXCHANGE)
        results_to_file_th.setName('results_to_file')
        results_to_file_th.run()

    else:
        print("Starting AUTOMATED INTEROP DRIVER..")
        pft = PerformFullTest(
            run_all_tests_cases=True,
            use_special_delimiters_for_report=True,
            dump_results_to_files=False
        )
        pft.run()
        pft.stop()
