# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import subprocess
from automated_IUTs import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST
from automated_IUTs.automation import *

str_coap_server_port = str(COAP_SERVER_PORT)


class CaliforniumCoapClient(AutomatedIUT):
    component_id = 'automated_iut'
    node = 'coap_client'
    iut_cmd = [
        'java -jar automated_IUTs/coap_client_californium/target/coap_plugtest_client-1.1.0-SNAPSHOT.jar -s -u coap://['
        + COAP_SERVER_HOST + ']:' + str_coap_server_port + ' -t'
    ]

    # mapping message's stimuli id -> CoAPthon (coap client) commands
    stimuli_cmd_dict = {
        'TD_COAP_CORE_01_v01_step_01': iut_cmd + ['TD_COAP_CORE_01'],
        'TD_COAP_CORE_02_v01_step_01': iut_cmd + ['TD_COAP_CORE_02'],
        'TD_COAP_CORE_03_v01_step_01': iut_cmd + ['TD_COAP_CORE_03'],
        'TD_COAP_CORE_04_v01_step_01': iut_cmd + ['TD_COAP_CORE_04'],
        'TD_COAP_CORE_05_v01_step_01': iut_cmd + ['TD_COAP_CORE_05'],
        'TD_COAP_CORE_06_v01_step_01': iut_cmd + ['TD_COAP_CORE_06'],
        'TD_COAP_CORE_07_v01_step_01': iut_cmd + ['TD_COAP_CORE_07'],
        'TD_COAP_CORE_08_v01_step_01': iut_cmd + ['TD_COAP_CORE_08'],
        'TD_COAP_CORE_09_v01_step_01': iut_cmd + ['TD_COAP_CORE_09'],
        'TD_COAP_CORE_10_v01_step_01': iut_cmd + ['TD_COAP_CORE_10'],
        'TD_COAP_CORE_11_v01_step_01': iut_cmd + ['TD_COAP_CORE_11'],
        'TD_COAP_CORE_12_v01_step_01': iut_cmd + ['TD_COAP_CORE_12'],
        'TD_COAP_CORE_13_v01_step_01': iut_cmd + ['TD_COAP_CORE_13'],
        'TD_COAP_CORE_14_v01_step_01': iut_cmd + ['TD_COAP_CORE_14'],
        'TD_COAP_CORE_17_v01_step_01': iut_cmd + ['TD_COAP_CORE_17'],
        'TD_COAP_CORE_18_v01_step_01': iut_cmd + ['TD_COAP_CORE_18'],
        'TD_COAP_CORE_19_v01_step_01': iut_cmd + ['TD_COAP_CORE_19'],
        'TD_COAP_CORE_20_v01_step_01': iut_cmd + ['TD_COAP_CORE_20'],
        'TD_COAP_CORE_20_v01_step_05': None,
        'TD_COAP_CORE_21_v01_step_01': iut_cmd + ['TD_COAP_CORE_21'],
        'TD_COAP_CORE_21_v01_step_05': None,
        'TD_COAP_CORE_21_v01_step_09': None,
        'TD_COAP_CORE_21_v01_step_10': None,
        'TD_COAP_CORE_22_v01_step_01': iut_cmd + ['TD_COAP_CORE_22'],
        'TD_COAP_CORE_22_v01_step_04': None,
        'TD_COAP_CORE_22_v01_step_08': None,
        'TD_COAP_CORE_22_v01_step_12': None,
        'TD_COAP_CORE_22_v01_step_13': None,
        'TD_COAP_CORE_23_v01_step_01': iut_cmd + ['TD_COAP_CORE_23'],
        'TD_COAP_CORE_23_v01_step_05': None,

    }

    implemented_testcases_list = [
        'TD_COAP_CORE_01_v01',
        'TD_COAP_CORE_02_v01',
        'TD_COAP_CORE_03_v01',
        'TD_COAP_CORE_04_v01',
        'TD_COAP_CORE_05_v01',
        'TD_COAP_CORE_06_v01',
        'TD_COAP_CORE_07_v01',
        'TD_COAP_CORE_08_v01',
        'TD_COAP_CORE_09_v01',
        'TD_COAP_CORE_10_v01',
        'TD_COAP_CORE_11_v01',
        'TD_COAP_CORE_12_v01',
        'TD_COAP_CORE_13_v01',
        'TD_COAP_CORE_14_v01',
        'TD_COAP_CORE_17_v01',
        'TD_COAP_CORE_18_v01',
        'TD_COAP_CORE_19_v01',
        'TD_COAP_CORE_20_v01',
        'TD_COAP_CORE_21_v01',
        'TD_COAP_CORE_22_v01',
        'TD_COAP_CORE_23_v01',
    ]

    def _execute_verify(self, verify_step_id, ):
        logging.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, cmd):
        try:
            logging.info('spawning process with : %s' % cmd)
            cmd = " ".join(cmd)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
            proc.wait(timeout=STIMULI_HANDLER_TOUT)
            output = ''
            while proc.poll() is None:
                output += str(proc.stdout.readline())
            output += str(proc.stdout.read())
            logging.info('%s executed' % stimuli_step_id)
            logging.info('process stdout: %s' % output)

        except subprocess.TimeoutExpired as tout:
            logging.warning('Process timeout. info: %s' % str(tout))


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    iut = CaliforniumCoapClient()
    iut.start()
    iut.join()
