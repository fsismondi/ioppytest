# -*- coding: utf-8 -*-
# !/usr/bin/env python3
import sys
import yaml
import pika
import tabulate
import argparse
import threading

from messages import *
from ioppytest import AMQP_URL, AMQP_EXCHANGE, LOG_LEVEL, TEST_DESCRIPTIONS_CONFIGS, LOGGER_FORMAT
from ioppytest.test_suite.testsuite import TestConfig, get_dict_of_all_test_cases_configurations
from event_bus_utils import publish_message
from event_bus_utils.rmq_handler import RabbitMQHandler, JsonFormatter

COMPONENT_ID = 'packet_router'

logging.basicConfig(
    level=LOG_LEVEL,
    format=LOGGER_FORMAT
)

logging.getLogger('pika').setLevel(logging.WARNING)


class PacketRouter(threading.Thread):
    DEFAULT_TOPICS = [
        'routing.#',
    ]  # this list is further extended on __init__ with the routing table

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

        self.logger.info('routing table (rkey_src:[rkey_dst]) : \n{table}'.format(
            table=tabulate.tabulate([[k, list(v)] for k, v in self.routing_table.items()], tablefmt="grid")
        ))

        self.message_count = 0
        self.pending_number_of_packets_to_drop = 0
        self._set_up_connection()
        self._queues_init()

        msg = MsgTestingToolComponentReady(
            component='packetrouting'
        )
        publish_message(self.connection, msg)

        self.logger.info('Waiting for new messages in the data plane..')

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
            self.logger.error(' AMQP connection cannot be established, is message broker up? \n More: %s' % cc)
            sys.exit(1)

    def _queues_init(self):
        # declare a multi-purpose amqp queue for services provided by component
        self.channel.queue_declare(queue='services_queue@%s' % COMPONENT_ID, auto_delete=True)
        self.channel.queue_purge('services_queue@%s' % COMPONENT_ID)

        for t in self.DEFAULT_TOPICS:
            self.channel.queue_bind(exchange=self.exchange_name,
                                    queue='services_queue@%s' % COMPONENT_ID,
                                    routing_key=t)

            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(on_message_callback=self._on_request, queue='services_queue@%s' % COMPONENT_ID)

        # handle subscriptions for routing table declarations
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
            self.channel.basic_consume(on_message_callback=self._on_request, queue=src_queue)

    def stop(self):

        self._notify_component_shutdown()

        # delete routing all queues
        for src_rkey in self.routing_table.keys():
            # convention on queue naming
            src_queue = '%s@%s' % (src_rkey, COMPONENT_ID)
            self.channel.queue_delete(src_queue)

        self.channel.stop_consuming()

    def _on_request(self, ch, method, props, body):

        # ack message received
        ch.basic_ack(delivery_tag=method.delivery_tag)

        self.logger.info('Identifying request with rkey: %s' % method.routing_key)

        try:
            msg_received = Message.load_from_pika(method, props, body)
            print(msg_received.routing_key)
        except Exception as e:
            self.logger.info(str(e))
            return

        if isinstance(msg_received, MsgPacketSniffedRaw):

            self.message_count += 1
            if self.pending_number_of_packets_to_drop > 0:
                self.pending_number_of_packets_to_drop -= 1
                self.logger.info(
                    'Dropping packet due to lossy link config. Pending packets to drop: %s' %
                    self.pending_number_of_packets_to_drop
                )
                return

            # let's route the message to the right agent
            try:
                msg_to_send = MsgPacketInjectRaw(
                    data=msg_received.data,
                    timestamp=msg_received.timestamp,
                    interface_name=msg_received.interface_name
                )
            except:
                self.logger.error(
                    'wrong message format, <data> , <timestamp> and <interface_name> fields expected, got: {msg}'.
                        format(msg=repr(msg_received))
                )
                return

            src_rkey = msg_received.routing_key
            json_to_send = msg_to_send.to_json()
            if src_rkey in self.routing_table.keys():
                list_dst_rkey = self.routing_table[src_rkey]
                for dst_rkey in list_dst_rkey:
                    # forward to dst_rkey
                    self.channel.basic_publish(
                        body=json_to_send,
                        routing_key=dst_rkey,
                        exchange=self.exchange_name,
                        properties=pika.BasicProperties(
                            content_type='application/json',
                        )
                    )

                    self.logger.info(
                        "Routing packet (%d) from topic: %s to topic: %s" % (self.message_count, src_rkey, dst_rkey))

            elif 'toAgent' in src_rkey:
                pass  # this is probably a message echo'ed from a message sent by this same component

            else:
                self.logger.warning('No known route for r_key source: {r_key}'.format(r_key=src_rkey))
                return

        elif isinstance(msg_received, MsgRoutingStartLossyLink):
            self.pending_number_of_packets_to_drop = msg_received.number_of_packets_to_drop
            self.logger.info("Packet router configured to drop %s packet(s)" % self.pending_number_of_packets_to_drop)
        else:
            self.logger.warning("Message ignored %s" % repr(msg_received))

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
    """
    Builds routing table (not IP based, but using amqp topics), example for COAP_CFG_01

    ----------------------------------------------  --------------------------------------------------------------------
    data.serial.fromAgent.coap_client               ['data.serial.toAgent.coap_server', 'data.serial.toAgent.agent_TT']
    fromAgent.coap_client.802154.serial.packet.raw  ['toAgent.coap_server.802154.serial.packet.raw', 'toAgent.agent_...
    fromAgent.coap_client.ip.tun.packet.raw         ['toAgent.coap_server.ip.tun.packet.raw', 'toAgent.agent_TT.ip.t...
    data.serial.fromAgent.coap_server               ['data.serial.toAgent.coap_client', 'data.serial.toAgent.agent_T...
    fromAgent.coap_server.802154.serial.packet.raw  ['toAgent.coap_client.802154.serial.packet.raw', 'toAgent.agent_...
    fromAgent.coap_server.ip.tun.packet.raw         ['toAgent.coap_client.ip.tun.packet.raw', 'toAgent.agent_TT.ip.t...
    data.serial.fromAgent.agent_TT                  ['data.serial.toAgent.coap_client', 'data.serial.toAgent.coap_se...
    fromAgent.agent_TT.802154.serial.packet.raw     ['toAgent.coap_client.802154.serial.packet.raw', 'toAgent.coap_s...
    fromAgent.agent_TT.ip.tun.packet.raw            ['toAgent.coap_client.ip.tun.packet.raw', 'toAgent.coap_server.i...
    ----------------------------------------------  --------------------------------------------------------------------
    :param testconfig:
    :return:
    """

    assert testconfig.nodes
    assert len(testconfig.nodes) >= 2

    agent_tt = 'agent_TT'
    routing_table = dict()

    for link in testconfig.topology:
        link_routes = {}

        # I assume node to node links (this MUST be like this for any ioppytest interop test)

        nodes = link['nodes'].copy()
        nodes.append(agent_tt)  # every single packet needs to be forwarded to agent TT
        logging.info("Configuring routing tables for nodes: %s" % nodes)

        # TODO deprecate old API from 802.15.4 based test suites like sixlowpan
        table_entry_from_serial_v0 = "data.serial.fromAgent.{node}"
        table_entry_to_serial_v0 = "data.serial.toAgent.{node}"

        table_entry_from_serial_v1 = "fromAgent.{node}.802154.serial.packet.raw"
        table_entry_to_serial_v1 = "toAgent.{node}.802154.serial.packet.raw"

        table_entry_from_tun = "fromAgent.{node}.ip.tun.packet.raw"
        table_entry_to_tun = "toAgent.{node}.ip.tun.packet.raw"

        for i in nodes:
            # # routes for agents' serial interfaces (802.15.4 nodes) # #

            # API version v.0.1 (ToDO deprecate legacy stuff)
            link_routes[table_entry_from_serial_v0.format(node=i)] = [table_entry_to_serial_v0.format(node=j) for j in
                                                                      nodes if j != i]
            # API v.1.0 [toAgent|fromAgent.*.802154.serial.packet.raw]
            link_routes[table_entry_from_serial_v1.format(node=i)] = [table_entry_to_serial_v1.format(node=j) for j in
                                                                      nodes if j != i]

            # # routes for agents' TUNs interfaces (ipv6 nodes) # #

            # API v.1.0 [toAgent|fromAgent.*.ip.tun.packet.raw]
            link_routes[table_entry_from_tun.format(node=i)] = [table_entry_to_tun.format(node=j) for j in
                                                                nodes if j != i]

            routing_table.update(link_routes)
            # print(tabulate.tabulate([*routing_table.items()]))

    return routing_table


def main():
    td_config = get_dict_of_all_test_cases_configurations()

    assert len(td_config) > 0, 'No test case configuration files found!'

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
