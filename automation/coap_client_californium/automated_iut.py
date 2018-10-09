# -*- coding: utf-8 -*-
# !/usr/bin/env python3

from automation import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST, LOG_LEVEL
from automation.automated_iut import *

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

default_coap_server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST


class AutomatedCaliforniumCoapClient(AutomatedIUT):
    """
    californium client CLI expects:
    java -jar (..)/coap_plugtest_client-1.1.0-SNAPSHOT.jar -s -u coap://[<IPv6>]:port -t TD_COAP_CORE_01
    """

    component_id = 'automated_iut-coap_client-californium'
    node = 'coap_client'
    iut_base_cmd = 'java -jar automation/coap_client_californium/target/coap_plugtest_client-1.1.0-SNAPSHOT.jar -s'

    # mapping message's stimuli id -> testcase id
    stimuli_to_testcase_map = {
        'TD_COAP_CORE_01_step_01': 'TD_COAP_CORE_01',
        'TD_COAP_CORE_02_step_01': 'TD_COAP_CORE_02',
        'TD_COAP_CORE_03_step_01': 'TD_COAP_CORE_03',
        'TD_COAP_CORE_04_step_01': 'TD_COAP_CORE_04',
        'TD_COAP_CORE_05_step_01': 'TD_COAP_CORE_05',
        'TD_COAP_CORE_06_step_01': 'TD_COAP_CORE_06',
        'TD_COAP_CORE_07_step_01': 'TD_COAP_CORE_07',
        'TD_COAP_CORE_08_step_01': 'TD_COAP_CORE_08',
        'TD_COAP_CORE_09_step_01': 'TD_COAP_CORE_09',
        'TD_COAP_CORE_10_step_01': 'TD_COAP_CORE_10',
        'TD_COAP_CORE_11_step_01': 'TD_COAP_CORE_11',
        'TD_COAP_CORE_12_step_01': 'TD_COAP_CORE_12',
        'TD_COAP_CORE_13_step_01': 'TD_COAP_CORE_13',
        'TD_COAP_CORE_14_step_01': 'TD_COAP_CORE_14',
        'TD_COAP_CORE_17_step_01': 'TD_COAP_CORE_17',
        'TD_COAP_CORE_18_step_01': 'TD_COAP_CORE_18',
        'TD_COAP_CORE_19_step_01': 'TD_COAP_CORE_19',
        'TD_COAP_CORE_20_step_01': 'TD_COAP_CORE_20',
        'TD_COAP_CORE_21_step_01': 'TD_COAP_CORE_21',
        'TD_COAP_CORE_22_step_01': 'TD_COAP_CORE_22',
        'TD_COAP_CORE_23_step_01': 'TD_COAP_CORE_23',

    }

    implemented_stimuli_list = list(stimuli_to_testcase_map.keys())
    implemented_testcases_list = list(stimuli_to_testcase_map.values())

    def __init__(self):
        super().__init__(self.node)
        logger.info('starting %s  [ %s ]' % (self.node, self.component_id))

    def _execute_verify(self, verify_step_id):
        logger.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, addr):

        logger.info('got stimuli execute request: \n\tSTIMULI_ID=%s,\n\tTARGET_ADDRESS=%s' % (stimuli_step_id, addr))

        if addr and addr is not "":
            target_base_url = 'coap://[%s]:%s' % (addr, COAP_SERVER_PORT)
        else:
            target_base_url = default_coap_server_base_url
        try:

            # Generate IUT CMD for stimuli

            cmd = self.iut_base_cmd
            cmd += ' {option} {value}'.format(option='-u', value=target_base_url)
            cmd += ' {option} {value}'.format(option='-t', value=self.stimuli_to_testcase_map[stimuli_step_id])

            # Execute IUT CMD for stimuli
            logger.info('Spawning process with : %s' % cmd)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
            proc.wait(timeout=STIMULI_HANDLER_TOUT)

            # GET stdout IUT CMD for stimuli
            output = ''
            while proc.poll() is None:
                output += str(proc.stdout.readline())
            output += str(proc.stdout.read())
            logger.info('EXECUTED: %s' % stimuli_step_id)
            logger.info('Process STDOUT: %s' % output)

        except subprocess.TimeoutExpired as tout:
            logger.warning('Process TIMEOUT. info: %s' % str(tout))

        except Exception as e:
            logging.error('Error found on automated-iut while tryning to execute stimuli %s' % stimuli_step_id)
            logging.error(e)

    def _execute_configuration(self, testcase_id, node):
        # no config / reset needed for implementation
        return coap_host_address


if __name__ == '__main__':

    try:
        iut = AutomatedCaliforniumCoapClient()
        iut.start()
        iut.join()
    except Exception as e:
        logger.error(e)
