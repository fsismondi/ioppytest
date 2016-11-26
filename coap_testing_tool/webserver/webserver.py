# -*- coding: utf-8 -*-
#!/usr/bin/env python3
from coap_testing_tool import LOGDIR
from coap_testing_tool.utils.logger import initialize_logger
from http.server import BaseHTTPRequestHandler, HTTPServer
from multiprocessing import Process
import os, errno, logging

COMPONENT_ID = 'webserver'
#LOGDIR = '/Users/fsismondi/git/coap_testing_tool/log/'
print(LOGDIR)

class HTTPServer_RequestHandler(BaseHTTPRequestHandler):
    # GET
    def do_GET(self):
        # Send response status code
        self.send_response(200)

        # Send headers
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        print(LOGDIR)

        with open(os.path.join(LOGDIR,'all.log')) as f:
            cr = '<br/>'
            for line in f:
                # write the contents as bytes
                self.wfile.write(bytes(line + cr, 'utf-8'))
                # write the contents as bytes
                #self.wfile.write(bytes(cr, 'utf-8'))

        f.close()
        return


if __name__ == '__main__':


    #init logger to stnd output and log files
    initialize_logger(LOGDIR, COMPONENT_ID)


    def launchHttpServerLogger():
        logging.info('starting server...')
        # Server settings
        server_address = ('0.0.0.0', 8080)
        http_serv = HTTPServer(server_address, HTTPServer_RequestHandler)
        logging.info('running server...')
        http_serv.serve_forever()


    # start http server process
    http_server_p = Process(target=launchHttpServerLogger)
    http_server_p.start()