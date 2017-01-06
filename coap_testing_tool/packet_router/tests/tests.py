import unittest, logging, os
import time, json
import pika

#for running single: test python3 -m unittest test_module.TestClass.test_method

class PacketRouterTestCase(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)
        self.queue_name = 'unittest_packet_router'

        # rewrite default values with ENV variables
        self.AMQP_SERVER = str(os.environ['AMQP_SERVER'])
        self.AMQP_USER = str(os.environ['AMQP_USER'])
        self.AMQP_PASS = str(os.environ['AMQP_PASS'])
        self.AMQP_VHOST = str(os.environ['AMQP_VHOST'])
        self.AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])

        print('Env vars for AMQP connection succesfully imported')
        print(json.dumps(
                    {
                        'server': self.AMQP_SERVER,
                        'session': self.AMQP_VHOST,
                        'user': self.AMQP_USER,
                        'pass': '#' * len(self.AMQP_PASS),
                        'exchange': self.AMQP_EXCHANGE
                    }
        ))

        credentials = pika.PlainCredentials(self.AMQP_USER, self.AMQP_PASS)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=self.AMQP_SERVER,
            virtual_host=self.AMQP_VHOST,
            credentials = credentials))
        self.channel = self.connection.channel()

        #we need a clean start
        self.channel.queue_delete(queue=self.queue_name)

        time.sleep(1)

        # create and bind queue
        self.channel.queue_declare(queue=self.queue_name)
        self.channel.queue_bind(exchange=self.AMQP_EXCHANGE,
                           queue=self.queue_name,
                           routing_key='data.tun.#')

    def test_packet_routing(self):
        """
        tests
            - from.agent1 -> to.agent2
            - from.agent2 -> to.agent1
        :return:
        """

        # forging agent 1 message
        self.channel.basic_publish(
            body=json.dumps({'_type': 'packet.raw', 'data': 'hello world'}),
            routing_key='data.tun.fromAgent.agent1',
            exchange=self.AMQP_EXCHANGE,
        )
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

        # forging agent 1 message
        self.channel.basic_publish(
            body=json.dumps({'_type': 'packet.raw', 'data': 'hello world'}),
            routing_key='data.tun.fromAgent.agent2',
            exchange=self.AMQP_EXCHANGE,
        )

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

if __name__ == '__main__':
    unittest.test_packet_router_agent1_to_agent2()
    #python3 -m unittest coap_testing_tool.packet_router.tests.tests.PacketRouterTestCase.test_packet_router_agent1_to_agent2