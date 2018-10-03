# -*- coding: utf-8 -*-
# !/usr/bin/env python3

from automation.automated_iut import *
from ioppytest import TMPDIR, TD_LWM2M, TD_LWM2M_CFG
from ioppytest.test_suite.testsuite import TestSuite

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

lwm2m_client_ip_prefix, lwm2m_client_ip_host = TestSuite(TD_LWM2M, TD_LWM2M_CFG).get_node_address('lwm2m_client')
lwm2m_server_ip_prefix, lwm2m_server_ip_host = TestSuite(TD_LWM2M, TD_LWM2M_CFG).get_node_address('lwm2m_server')

class LeshanServerTrigger(AutomatedIUT):
    """
    Leshan Server trigger expects:
    nodejs trigger.js -s TD_LWM2M_1_INT_201_step_01
    """

    component_id = 'automated_iut-lwm2m_server-leshan'
    node = 'lwm2m_server'
    iut_base_cmd = 'nodejs automation/lwm2m_server_leshan/trigger.js'

    def __init__(self):
        super().__init__(self.node)
        logger.info('starting %s  [ %s ]' % (self.node, self.component_id))

    def _execute_verify(self, verify_step_id):
        logger.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, addr):

        logger.info('got stimuli execute request: \n\tSTIMULI_ID=%s,\n\tTARGET_ADDRESS=%s' % (stimuli_step_id, addr))

        try:

            # Generate IUT CMD for stimuli

            cmd = self.iut_base_cmd
            cmd += ' {option} {value}'.format(option='-s', value=self.stimuli_step_id)

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
        return "{}::{}".format(lwm2m_server_ip_prefix, lwm2m_server_ip_host)


if __name__ == '__main__':

    try:
        logger.info('*********************************************************************')
        iut = LeshanServerTrigger()
        iut.start()
        iut.join()
    except Exception as e:
        logger.error(e)
