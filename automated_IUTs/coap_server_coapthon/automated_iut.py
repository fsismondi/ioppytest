# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import subprocess
from automated_IUTs.automation import *
from automated_IUTs import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST

logger = logging.getLogger(__name__)

# timeout in seconds
STIMULI_HANDLER_TOUT = 10

signal.signal(signal.SIGINT, signal_int_handler)


class CoapthonCoapServer(AutomatedIUT):
    component_id = 'automated_iut-coap_server'
    node = 'coap_server'

    IUT_CMD = [
        'python',
        'automated_IUTs/coap_server_coapthon/CoAPthon/plugtest_coapserver.py ',
    ]


    def __init__(self):
        super().__init__(self.node)
        logging.info('starting %s  [ %s ]' % (self.node, self.component_id))
        # process is spawned by supervisord

    def _execute_verify(self, verify_step_id, ):
        logging.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)



if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    iut = CoapthonCoapServer()
    iut.start()
    iut.join()