import os
import logging
import webbrowser

from automation import UserMock
from ioppytest.webserver.webserver import create_html_test_results, FILENAME_HTML_REPORT


def open_test_results_with_browser():
    webbrowser.open('file://' + os.path.realpath(FILENAME_HTML_REPORT))


if __name__ == '__main__':
    #connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

    # e.g. for TD COAP CORE from 1 to 31
    #tc_list = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 3)]
    #u = UserMock(tc_list)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logging.info('Starting the user mock component')

    u = UserMock()
    u.start()
    u.join()

    #  finishing Session..
    create_html_test_results()
    open_test_results_with_browser()
