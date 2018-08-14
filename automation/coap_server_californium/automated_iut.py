# -*- coding: utf-8 -*-
# !/usr/bin/env python3
import os
import subprocess
import logging

from ioppytest import TMPDIR
from automation import COAP_SERVER_PORT, COAP_SERVER_HOST
from automation.automated_iut import AutomatedIUT, launch_long_automated_iut_process

# timeout in seconds
STIMULI_HANDLER_TOUT = 15

server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)

LOGGER_ID = 'automation|coap_server'


class AutomatedCaliforniumCoapServer(AutomatedIUT):
    component_id = 'automated_iut-coap_server-californium'
    node = 'coap_server'
    process_log_file = os.path.join(TMPDIR, component_id + '.log')
    implemented_testcases_list = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 31)]

    iut_cmd = [
        'java',
        '-jar',
        'automation/coap_server_californium/target/coap_plugtest_server-1.0-SNAPSHOT.jar',
        COAP_SERVER_HOST,
        COAP_SERVER_PORT,
    ]

    def __init__(self):
        super().__init__(self.node)
        self.log('Starting %s  [ %s ]' % (self.node, self.component_id))
        self.log('Spawning process %s' % str(self.iut_cmd))
        launch_long_automated_iut_process(
            cmd=self.iut_cmd,
            process_logfile=self.process_log_file
        )
        self.log('Started %s  [ %s ]' % (self.node, self.component_id))

    def _execute_configuration(self, testcase_id, node):
        # should we restart process?
        return COAP_SERVER_HOST

    def _execute_verify(self, verify_step_id):
        self.log('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, addr):
        pass

if __name__ == '__main__':
    try:
        iut = AutomatedCaliforniumCoapServer()
        iut.start()
        iut.join()
    except Exception as e:
        logging.error(e)
