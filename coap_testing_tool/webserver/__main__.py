from coap_testing_tool.webserver.webserver import *

if __name__ == '__main__':
    def launchHttpServerLogger():
        logging.info('starting server...')
        # Server settings
        server_address = ('0.0.0.0', 8080)
        http_serv = HTTPServer(server_address, SimpleHTTPRequestHandler)
        logging.info('running server...')
        http_serv.serve_forever()


    # start http server process
    http_server_p = Process(target=launchHttpServerLogger)
    http_server_p.start()