# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import subprocess
from automated_IUTs import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST, LOG_LEVEL
from automated_IUTs.automation import *

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

default_coap_server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST


class ADN(AutomatedIUT):
    """
    ADN implementation expects:
    java -jar (..)/adn.jar -h [bbbb::2] -p 5683 -ci server -cn server -o Cae-admin -t TD_M2M_NH_01
    """

    component_id = 'automated_iut-onem2m_client-etsi_adn'
    node = 'adn'
    iut_base_cmd = 'java -jar automation/onem2m_adn_etsi_implementation/target/adn/adn.jar -h [bbbb::2] -p 5683 -ci server -cn server -o Cae-admin -t'

    # mapping message's stimuli id -> testcase id
    stimuli_to_testcase_map = {
        'TD_M2M_NH_01_step_01': 'TD_M2M_NH_01',
        'TD_M2M_NH_06_step_01': 'TD_M2M_NH_06',
        'TD_M2M_NH_07_step_01': 'TD_M2M_NH_07',
        'TD_M2M_NH_08_step_01': 'TD_M2M_NH_08',
        'TD_M2M_NH_09_step_01': 'TD_M2M_NH_09',
        'TD_M2M_NH_10_step_01': 'TD_M2M_NH_10',
        'TD_M2M_NH_11_step_01': 'TD_M2M_NH_11',
        'TD_M2M_NH_12_step_01': 'TD_M2M_NH_12',
        'TD_M2M_NH_13_step_01': 'TD_M2M_NH_13',
        'TD_M2M_NH_14_step_01': 'TD_M2M_NH_14',
        'TD_M2M_NH_15_step_01': 'TD_M2M_NH_15',
        'TD_M2M_NH_17_step_01': 'TD_M2M_NH_17',
        'TD_M2M_NH_49_step_01': 'TD_M2M_NH_49',
        'TD_M2M_NH_50_step_01': 'TD_M2M_NH_50',
        'TD_M2M_NH_71_step_01': 'TD_M2M_NH_71',
        'TD_M2M_NH_72_step_01': 'TD_M2M_NH_72',
        'TD_M2M_NH_18_step_01': 'TD_M2M_NH_18',
        'TD_M2M_NH_19_step_01': 'TD_M2M_NH_19',
        'TD_M2M_NH_20_step_01': 'TD_M2M_NH_20',
        'TD_M2M_NH_21_step_01': 'TD_M2M_NH_21',
        'TD_M2M_NH_22_step_01': 'TD_M2M_NH_22',
        'TD_M2M_NH_23_step_01': 'TD_M2M_NH_23',
        'TD_M2M_NH_24_step_01': 'TD_M2M_NH_24',
        'TD_M2M_NH_25_step_01': 'TD_M2M_NH_25',
        'TD_M2M_NH_26_step_01': 'TD_M2M_NH_26',
        'TD_M2M_NH_27_step_01': 'TD_M2M_NH_27',
        'TD_M2M_NH_28_step_01': 'TD_M2M_NH_28',
        'TD_M2M_NH_29_step_01': 'TD_M2M_NH_29',
        'TD_M2M_NH_30_step_01': 'TD_M2M_NH_30',
        'TD_M2M_NH_31_step_01': 'TD_M2M_NH_31',
        'TD_M2M_NH_32_step_01': 'TD_M2M_NH_32',
        'TD_M2M_NH_33_step_01': 'TD_M2M_NH_33',
        'TD_M2M_NH_34_step_01': 'TD_M2M_NH_34',
        'TD_M2M_NH_35_step_01': 'TD_M2M_NH_36',
        'TD_M2M_NH_36_step_01': 'TD_M2M_NH_36',
        'TD_M2M_NH_37_step_01': 'TD_M2M_NH_37',
        'TD_M2M_NH_38_step_01': 'TD_M2M_NH_38',
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

        #if addr and addr is not "":
         #   target_base_url = 'coap://[%s]:%s' % (addr, COAP_SERVER_PORT)
        #else:
        #    target_base_url = default_coap_server_base_url
        try:

            # Generate IUT CMD for stimuli

            cmd = self.iut_base_cmd
            #cmd += ' {option} {value}'.format(option='-u', value=target_base_url)
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
        iut =  ADN()
        iut.start()
        iut.join()
    except Exception as e:
        logger.error(e)

