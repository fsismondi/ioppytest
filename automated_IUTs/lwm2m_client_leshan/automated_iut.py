# -*- coding: utf-8 -*-
# !/usr/bin/env python3
import subprocess

from automated_IUTs.automation import *
from ioppytest import TMPDIR, TD_LWM2M, TD_LWM2M_CFG
from ioppytest.test_suite.testsuite import TestSuite

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# timeout in seconds
STIMULI_HANDLER_TOUT = 15

lwm2m_client_ip_prefix, lwm2m_client_ip_host = TestSuite(TD_LWM2M, TD_LWM2M_CFG).get_node_address('lwm2m_client')
lwm2m_server_ip_prefix, lwm2m_server_ip_host = TestSuite(TD_LWM2M, TD_LWM2M_CFG).get_node_address('lwm2m_server')


class LwM2MClient(AutomatedIUT):
    component_id = 'automated_iut-lwm2m_client_leshan'
    node = 'lwm2m_client'
    process_log_file = os.path.join(TMPDIR, component_id + '.log')

    implemented_testcases_list = []  # special case: all test cases can be executed by IUT

    iut_cmd = [
        'java',
        '-jar',
        'automated_IUTs/lwm2m_client_leshan/target/leshan-last-client.jar',
        '-u',
        '[{ipv6_prefix}::{ipv6_host}]'.format(ipv6_prefix=lwm2m_server_ip_prefix,
                                              ipv6_host=lwm2m_server_ip_host),
    ]

    def __init__(self):
        super().__init__(self.node)
        logging.info('starting %s  [ %s ]' % (self.node, self.component_id))
        logging.info('spawning process %s' % str(self.iut_cmd))
        self._launch_automated_iut_process()

    def _execute_verify(self, verify_step_id, ):
        logging.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, addr):
        pass

    def _launch_automated_iut_process(self):
        logging.info("Launching IUT with: %s" % self.iut_cmd)
        logging.info('IUT-automated process logging into %s' % self.process_log_file)
        with open(self.process_log_file, "w") as outfile:
            subprocess.Popen(self.iut_cmd, stdout=outfile)  # subprocess.Popen does not block

    def _execute_configuration(self, testcase_id, node):
        # shoud we restart the process?
        return None


if __name__ == '__main__':

    try:
        iut = LwM2MClient()
        iut.start()
        iut.join()

    except Exception as e:
        logger.error(e)
