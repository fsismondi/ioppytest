import logging
import pprint
import socket
import unittest
from automated_IUTs.automation import AutomatedIUT
from automated_IUTs.coap_client_libcoap.automated_iut import LibcoapClient

"""
python3 -m pytest tests/test_automation.py -vvv
"""

class TestAutomation(unittest.TestCase):

    def test_check_l3_reachability(self):

        ip = "127.0.0.1"
        reachable = AutomatedIUT.test_l3_reachability(ip)
        assert reachable

        ip = "192.0.2.1" # Should never be reachable, see RFC 5737
        reachable = AutomatedIUT.test_l3_reachability(ip)
        assert not reachable

        try:
           s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        except:
           return #this test cannot be executed cause OS doesnt support IPV6

        # ip = "::1"
        # reachable = AutomatedIUT.test_l3_reachability(ip)
        # assert reachable

class TestAPI_coap_client_libcoap(unittest.TestCase):

    def setUp(self):
        self.client = LibcoapClient()

    def test_check_overwrite_properties(self):
        assert self.client.node
        assert self.client.handle_stimuli_execute()
    def
