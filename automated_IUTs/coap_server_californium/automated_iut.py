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
    implemented_testcases_list = NotImplementedField
    stimuli_cmd_dict = NotImplementedField

    iut_cmd = [
        'java -jar automated_IUTs/coap_server_californium/target/coap_plugtest_server-1.0-SNAPSHOT.jar ::1 ' + str(COAP_SERVER_PORT)

    ]

    def _execute_verify(self, verify_step_id, ):
        logging.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    iut = CoapthonCoapServer()
    iut.start()
    iut.join()
