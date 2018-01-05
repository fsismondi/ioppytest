# -*- coding: utf-8 -*-

from ioppytest import __all__
from ioppytest import get_from_environment

INTERACTIVE_SESSION = get_from_environment("INTERACTIVE_SESSION", True)
COAP_CLIENT_HOST = get_from_environment("COAP_CLIENT_HOST", 'bbbb::1')
COAP_SERVER_HOST = get_from_environment("COAP_SERVER_HOST", 'bbbb::2')
COAP_SERVER_PORT = get_from_environment("COAP_SERVER_PORT", '5683')

LOG_LEVEL = 30
