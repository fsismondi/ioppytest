# -*- coding: utf-8 -*-
# !/usr/bin/env python3
import os
import subprocess

from ioppytest import TMPDIR
#from automated_IUTs import COAP_SERVER_PORT, COAP_SERVER_HOST, COAP_CLIENT_HOST, LOG_LEVEL
from automation.automated_iut import *

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)


logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# timeout in seconds
STIMULI_HANDLER_TOUT = 15

class onem2mServer(AutomatedIUT):
    component_id = 'automated_iut-onem2m_server-eclipse_om2m'
    node = 'cse'
    process_log_file = os.path.join(TMPDIR, component_id + '.log')

    iut_cmd = [
        'sh',
        'automation/onem2m_cse_eclipse_om2m/in-cse/start.sh',
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
        logging.info("Launching IUT with: %s" % self.iut_cmd)
        logging.info('IUT-automated process logging into %s' % self.process_log_file)
        with open(self.process_log_file, "w") as outfile:
            subprocess.Popen(self.iut_cmd, stdout=outfile)  # subprocess.Popen does not block

    def _execute_configuration(self, testcase_id, node):
        # should we restart process?
        return None


if __name__ == '__main__':

    try:
        iut = onem2mServer()
        iut.start()
        iut.join()
    except Exception as e:
        logger.error(e)

