# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import subprocess
from ioppytest import TMPDIR
from automated_IUTs.automation import *
from automated_IUTs import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST, LOG_LEVEL

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# timeout in seconds
STIMULI_HANDLER_TOUT = 10

server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST


class CoapthonCoapServerIPv6(AutomatedIUT):
    component_id = 'automated_iut-coap_server-coapthon'
    node = 'coap_server'

    iut_cmd = [
        'python',
        'automated_IUTs/coap_server_coapthon/CoAPthon/plugtest_coapserver.py',
        '-i',
        '::1',
        '-p',
        '5683',
    ]

    def __init__(self):
        self.process_log_file = os.path.join(TMPDIR, self.component_id + self.__class__.__name__ + '.log')

        super().__init__(self.node)
        logging.info('starting %s  [ %s ]' % (self.node, self.component_id))
        logging.info('spawning process %s' % str(self.iut_cmd))

        self.th = threading.Thread(target=self._launch_automated_iut)
        self.th.daemon = True
        self.th.start()

    def _execute_verify(self, verify_step_id, ):
        logging.warning('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_stimuli(self, stimuli_step_id, addr):
        pass

    def _launch_automated_iut(self):
        # att this is a blocking function
        logging.info('IUT-automated process logging into %s' % self.process_log_file)
        with open(self.process_log_file, "w") as outfile:
            subprocess.call(self.iut_cmd, stdout=outfile)


class CoapthonCoapServerIPv4(CoapthonCoapServerIPv6):

    component_id = 'automated_iut-coap_server-coapthon'
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
    logger.info('Starting IUT process')
    logger.info('IUT process init')
    iut_v4 = CoapthonCoapServerIPv4()
    iut_v6 = CoapthonCoapServerIPv6()

    logger.info('IUT process starting..')
    iut_v4.start()
    iut_v6.start()
    logger.info('IUT process stopping..')
    iut_v6.join()
    iut_v4.join()
    logger.info('IUT process finished. Bye!..')