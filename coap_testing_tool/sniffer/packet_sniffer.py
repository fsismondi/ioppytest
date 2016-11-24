#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import hashlib
import pika
import json
import logging

PCAP_DIR = 'finterop/sniffer/dumps'
ALLOWED_EXTENSIONS = set(['pcap'])

logging.basicConfig(
    format='%(levelname)s:%(message)s',
    level=logging.WARNING
)

connection = pika.BlockingConnection(pika.ConnectionParameters(
        host='localhost'))

channel = connection.channel()

channel.queue_declare(queue='services_queue@packet_sniffer')

channel.queue_bind(exchange='default',
                       queue='services_queue@packet_sniffer',
                       routing_key='control.sniffing.service')

def on_request(ch, method, props, body):

    req_dict = json.loads(body.decode('utf-8'))
    print(req_dict)

    try:
        req_type = req_dict['_type']

    except Exception as e:
        # TODO forward errors to event bus
        raise e


    if req_type == 'sniffing.getCapture':
        logging.info("Encoding PCAP file into base64 ...")
        # TODO this is hardcoded to return always the same pcap (for testing)
        with open(PCAP_DIR+"/TD_COAP_CORE_01.pcap", "rb") as file:
            enc = base64.b64encode(file.read())

        response = json.dumps(
            {
                '_type': 'sniffing.getCapture',
                'filetype':'pcap_base64',
                'filename':'TD_CORE_COAP_01.pcap',
                'value': enc.decode("ascii")
            }
        )
        logging.info("Response ready, PCAP bytes: \n" + str(response))
        logging.info("Sending PCAP through the AMQP interface ...")
        ch.basic_publish(exchange='default',
                         routing_key=props.reply_to,
                         properties=pika.BasicProperties(correlation_id = \
                                                             props.correlation_id),
                         body=response)
        ch.basic_ack(delivery_tag = method.delivery_tag)
    else:
        response = {
            "_type":"sniffing.error",
            "value":"Wrong request received: %"%str(req_dict)
        }
        ch.basic_publish(exchange='default',
                         routing_key='control.sniffing.error',
                         body=response)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(on_request, queue='services_queue@packet_sniffer')

print(" [x] Awaiting RPC requests")
channel.start_consuming()