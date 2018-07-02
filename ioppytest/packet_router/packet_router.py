# -*- coding: utf-8 -*-
# !/usr/bin/env python3
import argparse
import sys
import threading

import pika
import yaml

from ioppytest import AMQP_URL, AMQP_EXCHANGE, LOG_LEVEL, TEST_DESCRIPTIONS_CONFIGS, LOGGER_FORMAT
from ioppytest.test_suite.testsuite import TestConfig
from ioppytest.utils.amqp_synch_call import publish_message
from ioppytest.utils.messages import *
from ioppytest.utils.rmq_handler import RabbitMQHandler, JsonFormatter

COMPONENT_ID = 'packet_router'

logging.basicConfig(
    level=LOG_LEVEL,
    format=LOGGER_FORMAT
)

logging.getLogger('pika').setLevel(logging.WARNING)


class PacketRouter(threading.Thread):
    def __init__(self, amqp_url, amqp_exchange, routing_table):
        assert routing_table

        threading.Thread.__init__(self)

        self.exchange_name = amqp_exchange
        self.url = amqp_url

        self.routing_table = routing_table

        # component identification & bus params
        self.component_id = COMPONENT_ID

        # init logging to stnd output and log files
        self.logger = logging.getLogger(self.component_id)
        self.logger.setLevel(LOG_LEVEL)

        self.logger.info('routing table (rkey_src:[rkey_dst]) : {table}'.format(table=json.dumps(self.routing_table)))

        self.message_count = 0
        self._set_up_connection()
        self._queues_init()

        msg = MsgTestingToolComponentReady(
            component='packetrouting'
        )
        publish_message(self.connection, msg)

        self.logger.info('packet router waiting for new messages in the data plane..')

    def _set_up_connection(self):

        # AMQP log handler with f-interop's json formatter
        rabbitmq_handler = RabbitMQHandler(self.url, self.component_id)
        json_formatter = JsonFormatter()
        rabbitmq_handler.setFormatter(json_formatter)
        self.logger.addHandler(rabbitmq_handler)

        try:
            self.logger.info('Setting up AMQP connection..')
            # setup AMQP connection
            self.connection = pika.BlockingConnection(pika.URLParameters(self.url))
            self.channel = self.connection.channel()
            self.channel.basic_qos(prefetch_count=1)

        except pika.exceptions.ConnectionClosed as cc:
            self.logger.error(' AMQP cannot be established, is message broker up? \n More: %s' % cc)
            sys.exit(1)

    def _queues_init(self):
        for src_rkey, dst_rkey_list in self.routing_table.items():
            assert type(src_rkey) is str
            assert type(dst_rkey_list) is list

            src_queue = '%s@%s' % (src_rkey, COMPONENT_ID)
            self.channel.queue_declare(queue=src_queue,
                                       auto_delete=False,
                                       arguments={'x-max-length': 100})

            # start with clean queues
            self.channel.queue_purge(src_queue)
            self.channel.queue_bind(exchange=self.exchange_name,
                                    queue=src_queue,
                                    routing_key=src_rkey)

            # bind all src queues to _on_request callback
            self.channel.basic_consume(self._on_request, queue=src_queue)

    def stop(self):

        self._notify_component_shutdown()

        # delete routing all queues
        for src_rkey in self.routing_table.keys():
            # convention on queue naming
            src_queue = '%s@%s' % (src_rkey, COMPONENT_ID)
            self.channel.queue_delete(src_queue)

        self.channel.stop_consuming()

    def _on_request(self, ch, method, props, body):

        # TODO implement forced message drop mechanism
        # obj hook so json.loads respects the order of the fields sent -just for visualization purposeses-
        body_dict = json.loads(body.decode('utf-8'), object_pairs_hook=OrderedDict)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        self.message_count += 1
        self.logger.info("Routing message, count %s" % self.message_count)

        # let's route the message to the right agent
        try:
            m = MsgPacketInjectRaw(data=body_dict['data'],
                                   timestamp=body_dict['timestamp'],
                                   interface_name=body_dict['interface_name'])
        except:
            self.logger.error('wrong message format, no data field found in : {msg}'.format(msg=json.dumps(body_dict)))
            return

        src_rkey = method.routing_key
        if src_rkey in self.routing_table.keys():
            self.logger.warning('No known route for r_key source: {r_key}'.format(r_key=src_rkey))
            list_dst_rkey = self.routing_table[src_rkey]
            for dst_rkey in list_dst_rkey:
                # forward to dst_rkey
                self.channel.basic_publish(
                    body=m.to_json(),
                    routing_key=dst_rkey,
                    exchange=self.exchange_name,
                    properties=pika.BasicProperties(
                        content_type='application/json',
                    )
                )
                self.logger.info(
                    "Routing packet (%d) from topic: %s to topic: %s" % (self.message_count, src_rkey, dst_rkey))

        elif 'toAgent' in src_rkey:
            pass  # echo of router message

        else:
            self.logger.warning('No known route for r_key source: {r_key}'.format(r_key=src_rkey))
            return

    def _notify_component_shutdown(self):

        # FINISHING... let's send a goodbye message
        msg = MsgTestingToolComponentShutdown(
            component=COMPONENT_ID,
            description="%s is out!. Bye!" % COMPONENT_ID
        )

        self.channel.basic_publish(
            body=msg.to_json(),
            routing_key=msg.routing_key,
            exchange=self.exchange_name,
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )

    def run(self):
        self.channel.start_consuming()
        self._notify_component_shutdown()


def generate_routing_table_from_test_configuration(testconfig: TestConfig):
    assert testconfig.nodes
    assert len(testconfig.nodes) >= 2

    agent_tt = 'agent_TT'

    for link in testconfig.topology:
        # I assume node to node links (this MUST be like this for any ioppytest interop test)
        assert len(link['nodes']) == 2

        nodes = link['nodes']

        logging.info("Configuring routing tables for nodes: %s" % nodes)

        # routes for agents' serial interfaces (802.15.4 nodes)
        serial_routes = {
            # TODO deprecate API v0.1
            'data.serial.fromAgent.%s' % nodes[0]:
                [
                    'data.serial.toAgent.%s' % nodes[1],
                    'data.serial.toAgent.%s' % 'agent_TT',
                ],
            'data.serial.fromAgent.%s' % nodes[1]:
                [
                    'data.serial.toAgent.%s' % nodes[0],
                    'data.serial.toAgent.%s' % 'agent_TT',
                ],

            # API v.1.0 [toAgent|fromAgent.*.802154.serial.packet.raw]
            'fromAgent.%s.802154.serial.packet.raw' % nodes[0]:
                [
                    'toAgent.%s.802154.serial.packet.raw' % nodes[1],
                    'toAgent.%s.802154.serial.packet.raw' % 'agent_TT',
                ],
            'fromAgent.%s.802154.serial.packet.raw' % nodes[1]:
                [
                    'toAgent.%s.802154.serial.packet.raw' % nodes[0],
                    'toAgent.%s.802154.serial.packet.raw' % 'agent_TT',
                ],
        }

        # routes for agents' TUNs interfaces (ipv6 nodes)
        tun_routes = {
            # TODO deprecate API v0.1
            'data.tun.fromAgent.%s' % nodes[0]:
                [
                    'data.tun.toAgent.%s' % nodes[1],
                    'data.tun.toAgent.%s' % 'agent_TT',
                ],
            'data.tun.fromAgent.%s' % nodes[1]:
                [
                    'data.tun.toAgent.%s' % nodes[0],
                    'data.tun.toAgent.%s' % 'agent_TT',
                ],
            # API v.1.0 [toAgent|fromAgent.*.ip.tun.packet.raw]
            'fromAgent.%s.ip.tun.packet.raw' % nodes[0]:
                [
                    'toAgent.%s.ip.tun.packet.raw' % nodes[1],
                    'toAgent.%s.ip.tun.packet.raw' % 'agent_TT',
                ],
            'fromAgent.%s.ip.tun.packet.raw' % nodes[1]:
                [
                    'toAgent.%s.ip.tun.packet.raw' % nodes[0],
                    'toAgent.%s.ip.tun.packet.raw' % 'agent_TT',
                ],
        }
        routing_table = dict()
        routing_table.update(serial_routes)
        routing_table.update(tun_routes)

        return routing_table


def main():
    td_config = {}

    for TD in TEST_DESCRIPTIONS_CONFIGS:
        with open(TD, "r", encoding="utf-8") as stream:
            configs = yaml.load_all(stream)
            for c in configs:
                logging.info("Configuration found: %s" % c.id)
                td_config[c.id] = c

    if len(td_config) == 0:
        raise Exception('No test case configuration files found!')

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "td_configuration_id",
            help="Test case configuration ID as indicated in yaml file",
            choices=list(td_config)
        )

        args = parser.parse_args()

    except Exception as e:
        print(e)

    testcase_config = td_config[args.td_configuration_id]
    agents_routing_table = generate_routing_table_from_test_configuration(testcase_config)

    # start amqp router thread
    r = PacketRouter(AMQP_URL, AMQP_EXCHANGE, agents_routing_table)
    try:
        r.start()
        r.join()
    except (KeyboardInterrupt, SystemExit):
        logging.info('got SIGINT. Bye bye!')
        r.stop()


###############################################################################

if __name__ == '__main__':
    main()
