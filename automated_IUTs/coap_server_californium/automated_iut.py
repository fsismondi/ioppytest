# -*- coding: utf-8 -*-
# !/usr/bin/env python3
import os
import subprocess

from coap_testing_tool import TMPDIR
from automated_IUTs import COAP_SERVER_PORT
from automated_IUTs.automation import *

logger = logging.getLogger(__name__)

# timeout in seconds
STIMULI_HANDLER_TOUT = 3600

signal.signal(signal.SIGINT, signal_int_handler)


class CaliforniumCoapServer(AutomatedIUT):
    component_id = 'automated_iut_californium'
    node = 'coap_server'
    implemented_testcases_list = NotImplementedField
    stimuli_cmd_dict = NotImplementedField
    process_log_file = os.path.join(TMPDIR, component_id + '.log')

    iut_cmd = [
        'java',
        '-jar',
        'automated_IUTs/coap_server_californium/target/coap_plugtest_server-1.0-SNAPSHOT.jar',
        ' ::1 ',
        COAP_SERVER_PORT,
    ]

    def __init__(self):
        super().__init__()
        logging.info('starting %s  [ %s ]' % (self.node, self.component_id))
        logging.info('spawning process %s' % str(self.iut_cmd))
        th = threading.Thread(target=self._launch_automated_iut)
        th.daemon = True
        th.start()

    def _execute_verify(self, verify_step_id, ):
        logging.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, cmd):
        pass

    def _launch_automated_iut(self):
        # att this is a blocking function
        logging.info('IUT-automated process logging into %s' % self.process_log_file)
        with open(self.process_log_file, "w") as outfile:
            subprocess.call(self.iut_cmd, stdout=outfile)


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    iut = CaliforniumCoapServer()
    iut.start()
    iut.join()
