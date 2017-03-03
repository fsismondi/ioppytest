#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import platform
import subprocess
import errno
import sys
import base64
import traceback
import pika
import logging
import json
from collections import OrderedDict
from coap_testing_tool.utils.amqp_synch_call import amqp_reply
from coap_testing_tool import TMPDIR, DATADIR, LOGDIR, AMQP_EXCHANGE, AMQP_URL
from coap_testing_tool.utils.rmq_handler import RabbitMQHandler, JsonFormatter

COMPONENT_ID = 'packet_sniffer'

ALLOWED_EXTENSIONS = set(['pcap'])
_last_capture = None

# init logging to stnd output and log files
logger = logging.getLogger(__name__)

# default handler
sh = logging.StreamHandler()
logger.addHandler(sh)

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)
logger.setLevel(logging.DEBUG)

def on_request(ch, method, props, body):

    global _last_capture

    # ack message received
    ch.basic_ack(delivery_tag=method.delivery_tag)
    req_dict = json.loads(body.decode('utf-8'))
    # horribly long composition of methods,but  needed for keeping the order of fields of the received json object
    logger.debug('[event queue callback] service request received on the queue: %s || %s'
                 % (method.routing_key, json.dumps(json.loads(body.decode('utf-8'),object_pairs_hook=OrderedDict))))

    try:
        req_type = req_dict['_type']
    except Exception as e:
        logger.error('No _type found on event meesage : %s'%str(req_dict))

    if method.routing_key in ('control.sniffing.info','control.sniffing.error','control.sniffing.service.reply'):
        # ignore echo message
        logger.debug('Ignoring echo message: %s with r_key:%s' %(str(req_dict),method.routing_key))
    elif req_type == 'sniffing.getcapture':
        logger.info('Processing %s request'%req_type)
        try:
            capture_id = req_dict['capture_id']
        except:

            if _last_capture:
                capture_id = _last_capture
            else:
                err_mess = 'No capture to return. Maybe testsuite not started yet?'
                #raise ApiMessageFormatError(message='No capture_id provided')
                logger.warning(err_mess)
                # lets build response
                response = OrderedDict()
                response.update({'_type': req_type})
                response.update({'ok': False})
                response.update({'message': err_mess})
                response.update({'error_code': 'TBD'})
                amqp_reply(ch, props, response)
                return

        try:
            file = TMPDIR +'/%s.pcap'%capture_id
        # check if the size of PCAP is not zero
            if os.path.getsize(file)== 0:
                #raise SnifferError(message='Problem encountered with the requested PCAP')
                logger.error('Problem encountered with the requested PCAP')
                return
        except FileNotFoundError as fne:
            logger.error('Coulnt retrieve file %s from dir'%file)
            return
            #raise

        logger.info("Encoding PCAP file into base64 ...")

        # do not dump into PCAP_DIR, coordinator puts the PCAPS
        with open(TMPDIR+"/%s.pcap"%capture_id, "rb") as file:
            enc = base64.b64encode(file.read())

        # lets build response
        response = OrderedDict()
        response.update({'_type': req_type})
        response.update({'ok': True})
        response.update({'file_enc':'pcap_base64'})
        response.update({'filename':'%s.pcap'%capture_id})
        response.update({'value': enc.decode("utf-8")})

        logger.info("Response ready, PCAP bytes: \n" + str(response))
        logger.info("Sending response through AMQP interface ...")

        amqp_reply(ch, props, response)

    elif req_type == 'sniffing.start':
        logger.info('Processing %s request' % req_type)
        try:
            capture_id = req_dict['capture_id']
        except:
            #raise ApiMessageFormatError(message='No capture_id provided')
            logger.error('No capture id provided')
            return

        filename = TMPDIR + '/' + capture_id + ".pcap"
        filter_if = ''

        try:
            filter_if = req_dict['filter_if']
        except:
            logger.warning('No interface (filter_if) name provided')

        try:
            filter_proto = req_dict['filter_proto']
        except:
            logger.warning('No filter_proto provided')


        # TODO delete if there's already a file with the capture_id

        try:
            _launch_sniffer(filename,filter_if,filter_proto)
        except:
            #raise SnifferError('Didnt succeed starting the capture')
            logger.error('Didnt succeed starting the capture')

        # lets keep track of the undergoing capture name
        _last_capture = capture_id

        # lets build response
        response = OrderedDict()
        response.update({'_type': req_type})
        response.update({'ok': True})
        amqp_reply(ch, props, response)

    elif req_type == 'sniffing.stop':

        logger.info('Processing %s request' % req_type)

        try:
            _stop_sniffer()
        except:
            logger.error('Didnt succeed stopping the sniffer')

        # lets build response
        response = OrderedDict()
        response.update({'_type': req_type})
        response.update({'ok': True})
        amqp_reply(ch, props, response)

    else:
        logger.error('Wrong request received: %s' % str(req_dict))

### IMPLEMENTATION OF SERVICES ###

def _launch_sniffer(filename, filter_if, filter_proto):
    logger.info('Launching packet capture..')

    if filter_proto is None:
        filter_proto=''

    if (filter_if is None ) or (filter_if==''):
        sys_type = platform.system()
        if sys_type == 'Darwin':
            filter_if = 'lo0'
        else:
            filter_if = 'lo'
            # TODO windows?

    # lets try to remove the filemame in case there's a previous execution of the TC
    try:
        params = 'rm ' + filename
        os.system(params)
    except:
        pass

    params = 'tcpdump -K -i ' + filter_if + ' -s 200 ' + ' -U -w ' + filename + ' ' + '&'
    os.system(params)
    logger.info('creating process tcpdump with: %s'%params)
    # TODO we need to catch tcpdump: <<tun0: No such device exists>> from stderr

    return True

def _stop_sniffer():
    proc = subprocess.Popen(["pkill", "-INT", "tcpdump"], stdout=subprocess.PIPE)
    proc.wait()
    logger.info('Packet capture stopped')
    return True


if __name__ == '__main__':

    # generate dirs
    for d in TMPDIR, DATADIR, LOGDIR:
        try:
            os.makedirs(d)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    ### SETUPING UP CONNECTION ###

    connection = None

    try:

        logger.info('Setting up AMQP connection..')

        # setup AMQP connection
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        channel = connection.channel()

        channel = connection.channel()

        channel.queue_declare(queue='services_queue@%s' % COMPONENT_ID)

        channel.queue_bind(exchange=AMQP_EXCHANGE,
                           queue='services_queue@%s' % COMPONENT_ID,
                           routing_key='control.sniffing.service')

    except pika.exceptions.ConnectionClosed as cc:
        logger.error(' AMQP cannot be established, is message broker up? \n More: %s' % traceback.format_exc())
        sys.exit(1)


    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(on_request, queue='services_queue@%s' % COMPONENT_ID)

    channel.basic_publish(
        body=json.dumps({'message': '%s is up!'%COMPONENT_ID,"_type": 'sniffing.ready'}),
        exchange=AMQP_EXCHANGE,
        routing_key='control.session.bootstrap',
        properties=pika.BasicProperties(
            content_type='application/json',
        )
    )

    try:
        logger.info("Awaiting AMQP requests on topic: control.sniffing.service")
        channel.start_consuming()
    except pika.exceptions.ConnectionClosed as cc:
        logger.error(' AMQP connection closed: %s' % str(cc))
        sys.exit(1)
    except KeyboardInterrupt as KI:
        logger.info('SIGINT')
    except Exception as e:
        logger.error(' Unexpected error \n More: %s' % traceback.format_exc())
        sys.exit(1)
    finally:
        #close AMQP connection
        if connection:
            connection.close()
        sys.exit(1)






