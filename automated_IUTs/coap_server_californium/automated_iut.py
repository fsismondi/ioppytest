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


class CaliforniumCoapServer(AutomatedIUT):
    component_id = 'automated_iut-coap_server-californium'
    node = 'coap_server'
    process_log_file = os.path.join(TMPDIR, component_id + '.log')

    implemented_testcases_list = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 31)]

    stimuli_cmd_dict = NotImplementedField

    iut_cmd = [
        'java',
        '-jar',
        'automated_IUTs/coap_server_californium/target/coap_plugtest_server-1.0-SNAPSHOT.jar',
        ' ::1 ',
        COAP_SERVER_PORT,
    ]

    def __init__(self):
        super().__init__(self.node)
        logging.info('starting %s  [ %s ]' % (self.node, self.component_id))
        logging.info('spawning process %s' % str(self.iut_cmd))
        th = threading.Thread(target=self._launch_automated_iut)
        th.daemon = True
        th.start()

    def _execute_verify(self, verify_step_id, ):
        logging.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, cmd, addr):
        pass

    def _launch_automated_iut(self):
        # att this is a blocking function
        logging.info('IUT-automated process logging into %s' % self.process_log_file)
        with open(self.process_log_file, "w") as outfile:
            subprocess.call(self.iut_cmd, stdout=outfile)

    def _execute_configuration(self, testcase_id, node):
        # shoud we restart californium process?
        return server_base_url

if __name__ == '__main__':
    iut = CaliforniumCoapServer()
    iut.start()
    iut.join()
