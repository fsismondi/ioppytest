# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import subprocess
from automated_IUTs import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST, LOG_LEVEL
from automated_IUTs.automation import *

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

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
        logger.info('starting %s  [ %s ]' % (self.node, self.component_id))

    # mapping message's stimuli id -> CoAPthon (coap client) commands
    stimuli_cmd_dict = {
        'TD_COAP_CORE_01_step_01': iut_cmd + ['test_td_coap_core_01'],
        'TD_COAP_CORE_02_step_01': iut_cmd + ['test_td_coap_core_02'],
        'TD_COAP_CORE_03_step_01': iut_cmd + ['test_td_coap_core_03'],
        'TD_COAP_CORE_04_step_01': iut_cmd + ['test_td_coap_core_04'],
        'TD_COAP_CORE_05_step_01': iut_cmd + ['test_td_coap_core_05'],
        'TD_COAP_CORE_06_step_01': iut_cmd + ['test_td_coap_core_06'],
        'TD_COAP_CORE_07_step_01': iut_cmd + ['test_td_coap_core_07'],
        'TD_COAP_CORE_08_step_01': iut_cmd + ['test_td_coap_core_08'],
        'TD_COAP_CORE_09_step_01': iut_cmd + ['test_td_coap_core_09'],
        'TD_COAP_CORE_10_step_01': iut_cmd + ['test_td_coap_core_10'],
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
    ]

    def _execute_verify(self, verify_step_id, ):
        logger.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, cmd, addr):
        try:
            logger.info('spawning process with : %s' % cmd)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
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
    iut = CoapthonCoapClient()
    iut.start()
    iut.join()
