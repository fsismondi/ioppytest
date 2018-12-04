import unittest
import logging
import os
import time
import json
import pika

from messages import MsgPacketInjectRaw
from ioppytest.packet_router.__main__ import PacketRouter
from ioppytest import AMQP_URL, AMQP_EXCHANGE

TIME_NEEDED_FOR_EVENT_TO_BE_ROUTED = 5  # estimation


class PacketRouterTestCase(unittest.TestCase):
    """
    python3 -m unittest tests/test_packet_router.py
    """

    def setUp(self):
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
        self.queue_name = 'testing_packet_router'

        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

        # we need a clean start
        self.channel.queue_delete(queue=self.queue_name)
        self.channel.basic_qos(prefetch_count=1)

        time.sleep(1)

        # create and bind queue
        self.channel.queue_declare(queue=self.queue_name, auto_delete=False)
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                                queue=self.queue_name,
                                routing_key='toAgent.#')

        logging.info('using AMQP vars: %s, %s' % (AMQP_URL, AMQP_EXCHANGE,))

        self.routing_table = {
            'fromAgent.agent1.ip.tun.packet.raw':
                ['toAgent.agent2.ip.tun.packet.raw'],  # routes to only one destination
            'fromAgent.agent2.ip.tun.packet.raw':
                ['toAgent.agent1.ip.tun.packet.raw'],  # routes to only one destination
        }

        # start packet router
        packet_router = PacketRouter(AMQP_URL, AMQP_EXCHANGE, self.routing_table)
        packet_router.daemon = True
        packet_router.start()

    def test_packet_routing(self):
        assert self.channel.is_open, 'no channel opened for tests'

        self._send_packet_fromAgent1()
        time.sleep(TIME_NEEDED_FOR_EVENT_TO_BE_ROUTED)
        method_frame, header_frame, body = self.channel.basic_get(self.queue_name)
        print(body)
        assert method_frame is not None, 'Expected to get a message, but nothing was received'
        self.channel.basic_ack(method_frame.delivery_tag)

        # now in the other direction:
        time.sleep(2)

        self._send_packet_fromAgent2()
        time.sleep(TIME_NEEDED_FOR_EVENT_TO_BE_ROUTED)
        method_frame, header_frame, body = self.channel.basic_get(self.queue_name)
        print(method_frame, header_frame, body)
        assert method_frame is not None, 'Expected to get a message, but nothing was received'
        self.channel.basic_ack(method_frame.delivery_tag)

    def _send_packet_fromAgent1(self):
        """
        tests
        :return:
        """
        m = MsgPacketInjectRaw()
        m.routing_key = list(self.routing_table.keys())[0]  # use first routing table entry
        self.channel.basic_publish(
            body=m.to_json(),
            routing_key=m.routing_key,
            exchange=AMQP_EXCHANGE,
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )

    def _send_packet_fromAgent2(self):
        """
        tests
        :return:
        """

        m = MsgPacketInjectRaw()
        m.routing_key = list(self.routing_table.keys())[1]  # use second routing table entry
        self.channel.basic_publish(
            body=m.to_json(),
            routing_key=m.routing_key,
            exchange=AMQP_EXCHANGE,
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )
