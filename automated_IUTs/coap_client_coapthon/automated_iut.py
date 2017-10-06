# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import subprocess
from automated_IUTs import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST
from automated_IUTs.automation import *

server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST


class CoapthonCoapClient(AutomatedIUT):
    component_id = 'automated_iut-coap_client-coapthon'
    node = 'coap_client'

    iut_cmd = [
        'python',
        'automated_IUTs/coap_client_coapthon/CoAPthon/finterop_interop_tests.py',
        '-t',
    ]

    def __init__(self):
        super().__init__(self.node)
        logging.info('starting %s  [ %s ]' % (self.node, self.component_id))


    # mapping message's stimuli id -> CoAPthon (coap client) commands
    stimuli_cmd_dict = {
        'TD_COAP_CORE_01_v01_step_01': iut_cmd + ['test_td_coap_core_01'],
        'TD_COAP_CORE_02_v01_step_01': iut_cmd + ['test_td_coap_core_02'],
        'TD_COAP_CORE_03_v01_step_01': iut_cmd + ['test_td_coap_core_03'],
        'TD_COAP_CORE_04_v01_step_01': iut_cmd + ['test_td_coap_core_04'],
        'TD_COAP_CORE_05_v01_step_01': iut_cmd + ['test_td_coap_core_05'],
        'TD_COAP_CORE_06_v01_step_01': iut_cmd + ['test_td_coap_core_06'],
        'TD_COAP_CORE_07_v01_step_01': iut_cmd + ['test_td_coap_core_07'],
        'TD_COAP_CORE_08_v01_step_01': iut_cmd + ['test_td_coap_core_08'],
        'TD_COAP_CORE_09_v01_step_01': iut_cmd + ['test_td_coap_core_09'],
        'TD_COAP_CORE_10_v01_step_01': iut_cmd + ['test_td_coap_core_10'],
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
    ]

    def _execute_verify(self, verify_step_id, ):
        logging.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, cmd, addr):
        try:
            logging.info('spawning process with : %s' % cmd)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            proc.wait(timeout=STIMULI_HANDLER_TOUT)
            output = ''
            while proc.poll() is None:
                output += str(proc.stdout.readline())
            output += str(proc.stdout.read())
            logging.info('%s executed' % stimuli_step_id)
            logging.info('process stdout: %s' % output)

        except subprocess.TimeoutExpired as tout:
            logging.warning('Process timeout. info: %s' % str(tout))

    def _execute_configuration(self, testcase_id, node):
        # no config / reset needed for implementation
        return coap_host_address

if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    iut = CoapthonCoapClient()
    iut.start()
    iut.join()
