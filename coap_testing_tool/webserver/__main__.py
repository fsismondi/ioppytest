import logging
from coap_testing_tool.webserver.webserver import *

COMPONENT_ID = 'webserver'

logger = logging.getLogger(__name__)


def launchHttpServerLogger():
    logging.info('starting server...')
    # Server settings
    server_address = ('127.0.0.1', 8080)
    http_serv = HTTPServer(server_address, SimpleHTTPRequestHandler)
    logging.info('running server...')
    http_serv.serve_forever()

if __name__ == '__main__':
    launchHttpServerLogger()
