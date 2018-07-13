import logging
import pprint
import unittest
from automated_IUTs.automation import AutomatedIUT

class TestAutomation(unittest.TestCase):
    """
    python3 -m pytest tests/tests.test_automation.py -vvv
    """

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
        ip = "::1"
        reachable = AutomatedIUT.test_l3_reachability(ip)
        assert reachable
