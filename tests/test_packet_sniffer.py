import unittest, logging, os
import time, json
import pika
from ioppytest.utils.messages import *
import multiprocessing
from ioppytest import AMQP_URL, AMQP_EXCHANGE
from ioppytest.utils.event_bus_utils import amqp_request, publish_message
from ioppytest.packet_sniffer.__main__ import Sniffer, DLT_RAW

"""
launch it as
    python3 -m unittest ioppytest.packet_sniffer.tests.SnifferTestCase
"""


class SnifferTestCase(unittest.TestCase):
    def setUp(self):
        logging.info('using AMQP vars: %s, %s' % (AMQP_URL, AMQP_EXCHANGE,))
        self.capture_id = "test_capture_id"
        self.routing_key_data_packet = 'fromAgent.someRandomIutRole.ip.tun.packet.raw'
        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

        def sniffer_run():
            sniffer = Sniffer(
                traffic_dlt=DLT_RAW,
                amqp_url=AMQP_URL,
                amqp_exchange=AMQP_EXCHANGE
            )
            sniffer.run()

        self.sniffer_as_a_process = multiprocessing.Process(
            target=sniffer_run,
            name='process_%s_%s' % (self.__class__.__name__, 'tests'),
            args=()
        )

        self.sniffer_as_a_process.start()

        logging.info('started sniffer as a process')

    def tearDown(self):
        publish_message(self.connection, MsgTestingToolTerminate())
        self.connection.close()
        self.sniffer_as_a_process.terminate()

    def test_integration(self):
        time.sleep(1)
        self._01_start_sniffer()
        self._02_get_capture_with_id()
        self._03_get_capture()
        self._04_stop_sniffer()

    def _01_start_sniffer(self):
        response = amqp_request(
            connection=self.connection,
            request_message=MsgSniffingStart(
                capture_id=self.capture_id
            ),
            component_id=self.__class__.__name__,
            retries=10
        )
        assert response.ok, 'Returned %s' % repr(response)

    def _02_get_capture_with_id(self):
        time.sleep(5)
        forged_agent_raw_packet = MsgPacketSniffedRaw()
        forged_agent_raw_packet.routing_key = self.routing_key_data_packet

        publish_message(self.connection, forged_agent_raw_packet)
        publish_message(self.connection, forged_agent_raw_packet)

        time.sleep(1)

        response = amqp_request(
            connection=self.connection,
            request_message=MsgSniffingGetCapture(
                capture_id=self.capture_id
            ),
            component_id=self.__class__.__name__,
            retries=10
        )

        assert response.ok, 'Returned %s' % repr(response)

        logging.info(repr(response))

    def _03_get_capture(self):
        time.sleep(5)
        forged_agent_raw_packet = MsgPacketSniffedRaw()
        forged_agent_raw_packet.routing_key = self.routing_key_data_packet

        publish_message(self.connection, forged_agent_raw_packet)
        publish_message(self.connection, forged_agent_raw_packet)

        time.sleep(1)

        response = amqp_request(
            connection=self.connection,
            request_message=MsgSniffingGetCaptureLast(),
            component_id=self.__class__.__name__,
            retries=10
        )

        assert response.ok, 'Returned %s' % repr(response)

        logging.info(repr(response))

    def _04_stop_sniffer(self):
        response = amqp_request(
            connection=self.connection,
            request_message=MsgSniffingStop(),
            component_id=self.__class__.__name__,
            retries=10
        )

        assert response.ok, 'Returned %s' % repr(response)
