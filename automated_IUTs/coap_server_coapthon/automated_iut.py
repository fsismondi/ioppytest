# -*- coding: utf-8 -*-
# !/usr/bin/env python3

from automated_IUTs.automation import *
from automated_IUTs import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST

logger = logging.getLogger()

# timeout in seconds
STIMULI_HANDLER_TOUT = 10

server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST


class CoapthonCoapServer(AutomatedIUT):
    component_id = 'automated_iut-coap_server-coapthon'
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

    def _execute_configuration(self, testcase_id, node):
        # shoud we restart californium process?
        return server_base_url


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    iut = CoapthonCoapServer()
    iut.start()
    iut.join()