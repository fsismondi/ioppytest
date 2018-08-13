# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import os
import logging
from ioppytest import TMPDIR
from automated_IUTs.automation import AutomatedIUT, launch_long_automated_iut_process
from automated_IUTs import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST, LOG_LEVEL

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# timeout in seconds
STIMULI_HANDLER_TOUT = 15

server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST


class AutomatedCoapthonCoapServerIPv6(AutomatedIUT):
    component_id = 'automated_iut-coap_server-coapthon-v6'
    node = 'coap_server'
    implemented_testcases_list = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 31)]

    iut_cmd = [
        'python',
        'automated_IUTs/coap_server_coapthon/CoAPthon/plugtest_coapserver.py',
        '-i',
        COAP_SERVER_HOST,
        '-p',
        COAP_SERVER_PORT,
    ]

    def __init__(self):
        self.process_log_file = os.path.join(TMPDIR, self.component_id + self.__class__.__name__ + '.log')
        super().__init__(self.node)
        self.log('Starting %s  [ %s ]' % (self.node, self.component_id))
        self.log('Spawning process %s' % str(self.iut_cmd))
        launch_long_automated_iut_process(self.iut_cmd, self.process_log_file)
        self.log('Start OK %s  [ %s ]' % (self.node, self.component_id))

    def _execute_verify(self, verify_step_id):
        self.log('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, addr):
        pass

    def _execute_configuration(self, testcase_id, node):
        # should we restart process?
        return COAP_SERVER_HOST


class AutomatedCoapthonCoapServerIPv4(AutomatedCoapthonCoapServerIPv6):
    """
    basically only redefines ip where to serve, the rest is the same..
    """
    component_id = 'automated_iut-coap_server-coapthon-v4'
    node = 'coap_server'

    iut_cmd = [
        'python',
        'automated_IUTs/coap_server_coapthon/CoAPthon/plugtest_coapserver.py',
        '-i',
        '127.0.0.1',
        '-p',
        '5683',
    ]


if __name__ == '__main__':
    try:
        logger.info('Starting IUT process')
        logger.info('IUT process init')
        iut_v4 = AutomatedCoapthonCoapServerIPv4()
        iut_v6 = AutomatedCoapthonCoapServerIPv6()

        logger.info('IUT process starting..')
        iut_v4.start()
        iut_v6.start()
        logger.info('IUT process stopping..')
        iut_v6.join()
        iut_v4.join()
        logger.info('IUT process finished. Bye!..')

    except Exception as e:
        logger.error(e)