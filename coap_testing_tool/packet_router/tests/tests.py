import unittest, logging, os
import time, json
import pika
from coap_testing_tool.packet_router.packet_router import PacketRouter
from coap_testing_tool import AMQP_URL, AMQP_EXCHANGE
"""
launch it as
    python3 -m unittest coap_testing_tool.packet_router.tests.tests.PacketRouterTestCase
for running single a single test:
    python3 -m unittest test_module.TestClass.test_method
"""

class PacketRouterTestCase(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)
        self.queue_name = 'testing_packet_router'

        self.connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        self.channel = self.connection.channel()

        #we need a clean start
        self.channel.queue_delete(queue=self.queue_name)

        time.sleep(1)

        # create and bind queue
        self.channel.queue_declare(queue=self.queue_name, auto_delete=True)
        self.channel.queue_bind(exchange=AMQP_EXCHANGE,
                           queue=self.queue_name,
                           routing_key='data.tun.#')
        # start packet router
        packet_router = PacketRouter(self.connection,None)
        packet_router.daemon=True
        packet_router.start()

    def test_packet_routing(self):
        """
        tests
            - from PacketRouter.AGENT_1_ID -> to PacketRouter.AGENT_2_ID
            - from PacketRouter.AGENT_2_ID -> to PacketRouter.AGENT_1_ID
        """

        self._send_packet_fromAgent1()

        time.sleep(1)
        method_frame, header_frame, body = self.channel.basic_get(self.queue_name)
        print(method_frame, header_frame, body)
        assert method_frame is not None
        self.channel.basic_ack(method_frame.delivery_tag)

        time.sleep(1)
        method_frame, header_frame, body = self.channel.basic_get(self.queue_name)
        print(method_frame, header_frame, body)
        assert method_frame is not None
        self.channel.basic_ack(method_frame.delivery_tag)

        # now in the other direction:
        time.sleep(2)

        self._send_packet_fromAgent2()

        time.sleep(1)
        method_frame, header_frame, body = self.channel.basic_get(self.queue_name)
        print(method_frame, header_frame, body)
        assert method_frame is not None
        self.channel.basic_ack(method_frame.delivery_tag)

        time.sleep(1)
        method_frame, header_frame, body = self.channel.basic_get(self.queue_name)
        print(method_frame, header_frame, body)
        assert method_frame is not None
        self.channel.basic_ack(method_frame.delivery_tag)

    def test_send_packet_fromAgent1(self):
        self._send_packet_fromAgent1()

    def test_send_packet_fromAgent2(self):
        self._send_packet_fromAgent2()

    def _send_packet_fromAgent1(self):
        """
        tests
        :return:
        """

        self.channel.basic_publish(
            body=json.dumps(
                    {
                        '_type': 'packet.sniffed.raw',
                        'data': [96, 0, 0, 0, 0, 56, 0, 1, 254, 128, 0, 0, 0, 0, 0, 0, 174, 188, 50, 255, 254, 205, 243, 139, 255, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 22, 58, 0, 1, 0, 5, 2, 0, 0, 143, 0, 166, 127, 0, 0, 0, 2, 4, 0, 0, 0, 255, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 255, 0, 0, 1, 4, 0, 0, 0, 255, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 255, 205, 243, 139],
                        'description':'hello world',
                     }
            ),
            routing_key='data.tun.fromAgent.%s'%PacketRouter.AGENT_1_ID,
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

        self.channel.basic_publish(
            body=json.dumps(
                    {
                        '_type': 'packet.sniffed.raw',
                        'data': [96, 0, 0, 0, 0, 56, 0, 1, 254, 128, 0, 0, 0, 0, 0, 0, 174, 188, 50, 255, 254, 205, 243, 139, 255, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 22, 58, 0, 1, 0, 5, 2, 0, 0, 143, 0, 166, 127, 0, 0, 0, 2, 4, 0, 0, 0, 255, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 255, 0, 0, 1, 4, 0, 0, 0, 255, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 255, 205, 243, 139],
                        'description':'hello world',
                     }
            ),
            routing_key='data.tun.fromAgent.%s'%PacketRouter.AGENT_2_ID,
            exchange=AMQP_EXCHANGE,
            properties=pika.BasicProperties(
                        content_type='application/json',
                )
        )


