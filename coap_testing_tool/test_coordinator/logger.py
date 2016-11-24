import logging
import os.path
from http.server import BaseHTTPRequestHandler, HTTPServer

COMPONENT_DIR = 'coap_testing_tool/test_coordinator'
LOGDIR = os.path.join( os.getcwd(), COMPONENT_DIR, 'log')


def initialize_logger(output_dir):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # create console handler and set level to info
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # create error file handler and set level to error
    handler = logging.FileHandler(os.path.join(output_dir, "error.log"), "w", encoding=None, delay="true")
    handler.setLevel(logging.ERROR)
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # create debug file handler and set level to debug
    handler = logging.FileHandler(os.path.join(output_dir, "all.log"), "w")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class HTTPServer_RequestHandler(BaseHTTPRequestHandler):
    # GET
    def do_GET(self):
        # Send response status code
        self.send_response(200)

        # Send headers
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        with open(os.path.join(LOGDIR,'all.log')) as f:
            cr = '<br/>'
            for line in f:
                # write the contents as bytes
                self.wfile.write(bytes(line, 'utf-8'))
                # write the contents as bytes
                self.wfile.write(bytes(cr, 'utf-8'))






        f.close()
        return

        # # Send message back to client
        # with open(os.path.join(LOGDIR,'all.log'), "r") as file:
        #     read_data = file.read()
        #
        #
        #
        #     # Write content as utf-8 data
        #     self.wfile.write(bytes(read_data),'utf-8')
        #     self.wfile.flush()
        #     return


