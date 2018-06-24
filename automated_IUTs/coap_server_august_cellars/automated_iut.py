# -*- coding: utf-8 -*-
# !/usr/bin/env python3
import os
import subprocess

from ioppytest import TMPDIR
from automated_IUTs import COAP_SERVER_PORT, COAP_SERVER_HOST, COAP_CLIENT_HOST, LOG_LEVEL
from automated_IUTs.automation import *

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# timeout in seconds
STIMULI_HANDLER_TOUT = 3600

server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST


class AugustCellarsCoapServer(AutomatedIUT):
    component_id = 'automated_iut-coap_server-AugustCellars'
    node = 'coap_server'
    process_log_file = os.path.join(TMPDIR, component_id + '.log')
    implemented_testcases_list = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 31)]

    iut_cmd = [
        'java',
        '-jar',
        'automated_IUTs/coap_server_august_cellars/target/coap_plugtest_server-1.0-SNAPSHOT.jar',
        COAP_SERVER_HOST,
        COAP_SERVER_PORT,
    ]

    def __init__(self):
        super().__init__(self.node)
        logging.info('starting %s  [ %s ]' % (self.node, self.component_id))
        logging.info('spawning process %s' % str(self.iut_cmd))
        self._launch_automated_iut_process()

    def _execute_verify(self, verify_step_id):
        logging.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, addr):
        pass

    def _launch_automated_iut_process(self):
        pass
        # logging.info("Launching IUT with: %s" % self.iut_cmd)
        # logging.info('IUT-automated process logging into %s' % self.process_log_file)
        # with open(self.process_log_file, "w") as outfile:
        #     subprocess.Popen(self.iut_cmd, stdout=outfile)  # subprocess.Popen does not block

    def _execute_configuration(self, testcase_id, node):
        # should we restart AugustCellars process?
        return server_base_url


if __name__ == '__main__':

    try:
        iut = AugustCellarsCoapServer()
        iut.start()
        iut.join()
    except Exception as e:
        logger.error(e)
