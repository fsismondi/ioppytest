import logging
import socket
from coap_testing_tool.webserver.webserver import *

COMPONENT_ID = 'webserver'

logger = logging.getLogger(__name__)

def launchHttpServer():
    logging.info('starting server...')
    # Server settings
    server_address = ('127.0.0.1', 8080)
    http_serv = HTTPServer(server_address, SimpleHTTPRequestHandler)
    logging.info('running server on IPv4, host %s '%server_address)
    http_serv.serve_forever()

class HTTPServerV6(HTTPServer):
  address_family = socket.AF_INET6

def launchHttpServerV6():
    logging.info('starting server...')
    # Server settings
    server_address = ('127.0.0.1', 8080)
    http_serv = HTTPServerV6(server_address, SimpleHTTPRequestHandler)
    logging.info('running server on IPv6, host %s '%server_address)
    http_serv.serve_forever()

if __name__ == '__main__':
    launchHttpServer()
    #launchHttpServerV6()
