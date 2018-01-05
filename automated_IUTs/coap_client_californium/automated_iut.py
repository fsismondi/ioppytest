# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import subprocess
from automated_IUTs import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST, LOG_LEVEL
from automated_IUTs.automation import *

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST


class CaliforniumCoapClient(AutomatedIUT):
    component_id = 'automated_iut-coap_client-californium'
    node = 'coap_client'
    iut_cmd = [
        'java -jar automated_IUTs/coap_client_californium/target/coap_plugtest_client-1.1.0-SNAPSHOT.jar -s -u ' +
        server_base_url + ' -t'
    ]

    # mapping message's stimuli id -> CoAPthon (coap client) commands
    stimuli_cmd_dict = {
        'TD_COAP_CORE_01_step_01': iut_cmd + ['TD_COAP_CORE_01'],
        'TD_COAP_CORE_02_step_01': iut_cmd + ['TD_COAP_CORE_02'],
        'TD_COAP_CORE_03_step_01': iut_cmd + ['TD_COAP_CORE_03'],
        'TD_COAP_CORE_04_step_01': iut_cmd + ['TD_COAP_CORE_04'],
        'TD_COAP_CORE_05_step_01': iut_cmd + ['TD_COAP_CORE_05'],
        'TD_COAP_CORE_06_step_01': iut_cmd + ['TD_COAP_CORE_06'],
        'TD_COAP_CORE_07_step_01': iut_cmd + ['TD_COAP_CORE_07'],
        'TD_COAP_CORE_08_step_01': iut_cmd + ['TD_COAP_CORE_08'],
        'TD_COAP_CORE_09_step_01': iut_cmd + ['TD_COAP_CORE_09'],
        'TD_COAP_CORE_10_step_01': iut_cmd + ['TD_COAP_CORE_10'],
        'TD_COAP_CORE_11_step_01': iut_cmd + ['TD_COAP_CORE_11'],
        'TD_COAP_CORE_12_step_01': iut_cmd + ['TD_COAP_CORE_12'],
        'TD_COAP_CORE_13_step_01': iut_cmd + ['TD_COAP_CORE_13'],
        'TD_COAP_CORE_14_step_01': iut_cmd + ['TD_COAP_CORE_14'],
        'TD_COAP_CORE_17_step_01': iut_cmd + ['TD_COAP_CORE_17'],
        'TD_COAP_CORE_18_step_01': iut_cmd + ['TD_COAP_CORE_18'],
        'TD_COAP_CORE_19_step_01': iut_cmd + ['TD_COAP_CORE_19'],
        'TD_COAP_CORE_20_step_01': iut_cmd + ['TD_COAP_CORE_20'],
        'TD_COAP_CORE_20_step_05': None,
        'TD_COAP_CORE_21_step_01': iut_cmd + ['TD_COAP_CORE_21'],
        'TD_COAP_CORE_21_step_05': None,
        'TD_COAP_CORE_21_step_09': None,
        'TD_COAP_CORE_21_step_10': None,
        'TD_COAP_CORE_22_step_01': iut_cmd + ['TD_COAP_CORE_22'],
        'TD_COAP_CORE_22_step_04': None,
        'TD_COAP_CORE_22_step_08': None,
        'TD_COAP_CORE_22_step_12': None,
        'TD_COAP_CORE_22_step_13': None,
        'TD_COAP_CORE_23_step_01': iut_cmd + ['TD_COAP_CORE_23'],
        'TD_COAP_CORE_23_step_05': None,

    }

    implemented_testcases_list = [
        'TD_COAP_CORE_01',
        'TD_COAP_CORE_02',
        'TD_COAP_CORE_03',
        'TD_COAP_CORE_04',
        'TD_COAP_CORE_05',
        'TD_COAP_CORE_06',
        'TD_COAP_CORE_07',
        'TD_COAP_CORE_08',
        'TD_COAP_CORE_09',
        'TD_COAP_CORE_10',
        'TD_COAP_CORE_11',
        'TD_COAP_CORE_12',
        'TD_COAP_CORE_13',
        'TD_COAP_CORE_14',
        'TD_COAP_CORE_17',
        'TD_COAP_CORE_18',
        'TD_COAP_CORE_19',
        'TD_COAP_CORE_20',
        'TD_COAP_CORE_21',
        'TD_COAP_CORE_22',
        'TD_COAP_CORE_23',
    ]

    def __init__(self):
        super().__init__(self.node)
        logger.info('starting %s  [ %s ]' % (self.node, self.component_id))

    def _execute_verify(self, verify_step_id, ):
        logger.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, cmd, addr):
        try:
            logger.info('spawning process with : %s' % cmd)
            cmd = " ".join(cmd)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
            proc.wait(timeout=STIMULI_HANDLER_TOUT)
            output = ''
            while proc.poll() is None:
                output += str(proc.stdout.readline())
            output += str(proc.stdout.read())
            logger.info('%s executed' % stimuli_step_id)
            logger.info('process stdout: %s' % output)

        except subprocess.TimeoutExpired as tout:
            logger.warning('Process timeout. info: %s' % str(tout))

        except Exception as e:
            logging.error('Error found on automated-iut while tryning to execute stimuli %s' % stimuli_step_id)
            logging.error(e)

    def _execute_configuration(self, testcase_id, node):
        # no config / reset needed for implementation
        return coap_host_address


if __name__ == '__main__':
    iut = CaliforniumCoapClient()
    iut.start()
    iut.join()
