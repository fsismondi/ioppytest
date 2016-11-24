# -*- coding: utf-8 -*-
#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
import os

COMPONENT_DIR = 'coap_testing_tool/test_coordinator'
LOGDIR = os.path.join( os.getcwd(), COMPONENT_DIR, 'log')

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