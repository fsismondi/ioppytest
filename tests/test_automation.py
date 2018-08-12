# -*- coding: utf-8 -*-

import logging
import pprint
import socket
import unittest
import subprocess
import traceback

from shutil import which
from automated_IUTs.automation import AutomatedIUT

# automated clients
from automated_IUTs.coap_client_libcoap.automated_iut import AutomatedLibcoapClient
from automated_IUTs.coap_client_aiocoap.automated_iut import AutomatedAiocoapClient
from automated_IUTs.coap_client_californium.automated_iut import AutomatedCaliforniumCoapClient
from automated_IUTs.coap_client_coapthon.automated_iut import AutomatedCoapthonCoapClient

# for testing CLI of clients
from automated_IUTs.coap_client_libcoap.automated_iut import (stimuli_to_libcoap_cli_call,
                                                              aux_stimuli_to_libcoap_cli_call)

# automated servers
from automated_IUTs.coap_server_californium.automated_iut import AutomatedCaliforniumCoapServer
from automated_IUTs.coap_server_coapthon.automated_iut import (AutomatedCoapthonCoapServerIPv6,
                                                               AutomatedCoapthonCoapServerIPv4)
from automated_IUTs.coap_server_august_cellars.automated_iut import AutomatedAugustCellarsCoapServer
"""
python3 -m pytest tests/test_automation.py -vvv
"""
LOCALHOST_server_ipv4_address = "127.0.0.1"
LOCALHOST_server_ipv6_address = "::1"
LOCALHOST_server_port = 5683
timeout_iut_reponse = 10


class TestAutomation(unittest.TestCase):
    def test_check_l3_reachability(self):

        ip = "127.0.0.1"
        reachable = AutomatedIUT.test_l3_reachability(ip)
        assert reachable

        ip = "192.0.2.1"  # Should never be reachable, see RFC 5737
        reachable = AutomatedIUT.test_l3_reachability(ip)
        assert not reachable

        try:
            s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        except:
            return  # this test cannot be executed cause OS doesnt support IPV6

            # ip = "::1"
            # reachable = AutomatedIUT.test_l3_reachability(ip)
            # assert reachable


def is_coap_server_listening(ip=LOCALHOST_server_ipv6_address, port=LOCALHOST_server_port):
    # fixme , support also ipv4
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    result = sock.connect_ex((ip, port))
    if result == 0:
        return True
    else:
        return False


def is_tool(name):
    """Check whether `name` is on PATH and marked as executable."""
    return which(name) is not None


def launch_process(cmd, process_logfile):
    logging.info("Launching process with: %s" % cmd)
    logging.info('Process logging into %s' % process_logfile)
    with open(process_logfile, "w", encoding='utf-8') as outfile:
        subprocess.Popen(cmd, stdout=outfile)  # subprocess.Popen does not block


class TestCoapClientLibcoap(unittest.TestCase):
    def setUp(self):
        self.iut = AutomatedLibcoapClient

    def test_overridden_properties(self):
        assert self.iut.node
        assert self.iut.component_id
        assert self.iut.implemented_testcases_list is not None  # this asserts True if value is []


class TestCoapClientAiocoap(TestCoapClientLibcoap):
    def setUp(self): self.iut = AutomatedAiocoapClient


class TestCoapClientCalifornium(TestCoapClientLibcoap):
    def setUp(self): self.iut = AutomatedCaliforniumCoapClient


class TestCoapClientCoapthon(TestCoapClientLibcoap):
    def setUp(self): self.iut = AutomatedCoapthonCoapClient


class TestCoapServerCalifornium(TestCoapClientLibcoap):
    def setUp(self): self.iut = AutomatedCaliforniumCoapServer


class TestCoapServerCoapthonV6(TestCoapClientLibcoap):
    def setUp(self): self.iut = AutomatedCoapthonCoapServerIPv6

class TestCoapServerCoapthonV4(TestCoapClientLibcoap):
    def setUp(self): self.iut = AutomatedCoapthonCoapServerIPv4

@unittest.skipIf(not is_tool('coap-client'), "IUT not supported in current environment")
class TestAPICoapClientLibcoapCliAgainstServer(unittest.TestCase):
    """
    Don't use parent class AutomatedIUT methods, IUT AMQP agnostic methods which simplifies setup of tests
    """

    def setUp(self):
        self.target_base_url = 'coap://[%s]:%s' % (LOCALHOST_server_ipv6_address, LOCALHOST_server_port)

        # # using coap.me coap server
        # self.target_base_url = 'coap://[%s]:%s' % ("2001:638:708:30da:223:24ff:fe93:e128", LOCALHOST_server_port)

        # implementation's API which is going to be tested
        self.client_class = AutomatedLibcoapClient

        # dummy server used so we dont get errors due to non-replied CoAP requests
        server_cmd = [
            'python',
            'automated_IUTs/coap_server_coapthon/CoAPthon/plugtest_coapserver.py',
            '-i',
            LOCALHOST_server_ipv6_address,
            '-p',
            str(LOCALHOST_server_port),
        ]
        # ToDO catch process already running error, or socket error due to port reuse and continue silently
        self.server_logfile = "{}.log".format('coapthon_plugtests_coapserver')
        try:
            launch_process(
                cmd=server_cmd,
                process_logfile=self.server_logfile
            )
        except socket.error:
            logging.info("server already running")

    def tearDown(self):
        if self.server_logfile:
            contents = open(self.server_logfile, encoding='utf-8',errors='ignore').read()
            logging.info('coap server logfile: %s' % self.server_logfile)
            logging.info('coap server logs: %s' % contents)

    def test_all_stimuli_execution_using_CLI(self):
        for func, args in stimuli_to_libcoap_cli_call.values():
            # update target base url
            args['base_url'] = self.target_base_url

            logging.info('running {} with:\n{}'.format(str(func), pprint.pformat(args, indent=4)))

            # run stimuli as process
            func(**args)

    def test_all_aux_stimuli_execution_using_CLI(self):
        for func, args in aux_stimuli_to_libcoap_cli_call.values():
            # update target base url
            args['base_url'] = self.target_base_url

            logging.info('running {} with:\n{}'.format(str(func), pprint.pformat(args, indent=4)))

            # run stimuli as process
            func(**args)

