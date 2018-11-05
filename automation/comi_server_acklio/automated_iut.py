# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import traceback
from ioppytest import TMPDIR
from automation import COAP_SERVER_PORT, COAP_SERVER_HOST, COAP_CLIENT_HOST, LOG_LEVEL
from automation.automated_iut import *

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST

# timeout in seconds
STIMULI_HANDLER_TOUT = 15


class AcklioCoMiServer(AutomatedIUT):
    component_id = 'automated_iut-comi_server-acklio'
    node = 'comi_server'
    process_log_file = os.path.join(TMPDIR, component_id + '.log')

    stimuli_to_testcase_map = {}
    implemented_stimuli_list = list(stimuli_to_testcase_map.keys())
    implemented_testcases_list = list(stimuli_to_testcase_map.values())

    iut_cmd = [
        './serverComi --yang-sid-path=./plugtests/ --datastore-path=./plugtests/ --read-ds-from-file=1  launch'
    ]

    def __init__(self):
        super().__init__(self.node)
        logging.info('starting %s  [ %s ]' % (self.node, self.component_id))
        logging.info('spawning process %s' % str(self.iut_cmd))
        #th = threading.Thread(target=self._launch_automated_iut)
        #th.daemon = True
        #th.start()

    def _launch_automated_iut(self):
        # att this is a blocking function
        logging.info('IUT-automated process logging into %s' % self.process_log_file)
        with open(self.process_log_file, "w") as outfile:
            try:
                subprocess.call(self.iut_cmd, stdout=outfile)
            except FileNotFoundError:
                os.chdir(os.path.join(os.path.abspath(sys.path[0]), 'automation/comi_server_acklio'))
                subprocess.call(self.iut_cmd, stdout=outfile)

    def _execute_verify(self, verify_step_id ):
        logging.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, addr):
        pass

    def _execute_configuration(self, testcase_id, node):
        # shoud we restart process?
        return server_base_url

if __name__ == '__main__':
    try:
        iut = AcklioCoMiServer()
        iut.start()
        iut.join()
    except:
        logger.error(traceback.format_exc())
