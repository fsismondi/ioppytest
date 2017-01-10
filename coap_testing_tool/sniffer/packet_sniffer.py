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
from collections import OrderedDict
import json
from coap_testing_tool.utils.amqp_synch_call import amqp_reply
from coap_testing_tool.utils.logger import  initialize_logger
from coap_testing_tool import TMPDIR, DATADIR, LOGDIR, AMQP_EXCHANGE, AMQP_USER, AMQP_SERVER, AMQP_PASS, AMQP_VHOST
from coap_testing_tool.utils.exceptions import ApiMessageFormatError, SnifferError

COMPONENT_ID = 'packet_sniffer'

ALLOWED_EXTENSIONS = set(['pcap'])

last_capture = None

def on_request(ch, method, props, body):

    global last_capture

    # ack message received
    ch.basic_ack(delivery_tag=method.delivery_tag)

    req_dict = json.loads(body.decode('utf-8'))

    # horribly long composition of methods,but  needed for keeping the order of fields of the received json object
    logger.debug('[event queue callback] service request received on the queue: %s || %s'
                 % (method.routing_key, json.dumps(json.loads(body.decode('utf-8'),object_pairs_hook=OrderedDict))))

    try:
        req_type = req_dict['_type']

    except Exception as e:
        # TODO forward errors to event bus
        logger.error('No _type found on event meesage : %s'%str(req_dict))
        #raise e

    if method.routing_key in ('control.sniffing.info','control.sniffing.error','control.sniffing.service.reply'):
        # ignore echo message
        logger.debug('Ignoring echo message: %s with r_key:%s' %(str(req_dict),method.routing_key))

    elif req_type == 'sniffing.getcapture':
        logger.info('Processing %s request'%req_type)
        try:
            capture_id = req_dict['capture_id']
        except:

            if last_capture:
                capture_id = last_capture
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
        last_capture = capture_id

        # lets build response
        response = OrderedDict()
        response.update({'_type': req_type})
        response.update({'ok': True})
        amqp_reply(ch, props, response)

    elif req_type == 'sniffing.stop':

        logger.info('Processing %s request' % req_type)
        # try:
        #     capture_id = req_dict['capture_id']
        # except:
        #     raise ApiMessageFormatError(message='No testcase id provided')

        try:
            _stop_sniffer()
        except:
            #raise SnifferError('Didnt succeed stopping the capture')
            logger.error('Didnt succeed stopping the capture')

        # lets build response
        response = OrderedDict()
        response.update({'_type': req_type})
        response.update({'ok': True})
        amqp_reply(ch, props, response)

    else:
        # response = OrderedDict()
        # response.update({'_type': req_type})
        # response.update({'ok': False})
        # response.update({'value': 'Wrong request received: %s' % str(req_dict)})
        #
        # amqp_reply(ch, props, response)
        logger.error('Wrong request received: %s' % str(req_dict))

### IMPLEMENTATION OF SERVICES ###

#sudo needed?
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

    # lets try removing the file in case there's a previous execution of the TC
    try:
        params = 'rm ' + filename
        os.system(params)
    except:
        pass


    params = 'tcpdump -i ' + filter_if +' -s 200 ' + ' -U -w '+ filename +' '+ filter_proto + '&'
    os.system(params)

    logger.info('creating process tcpdump with: %s'%params)

    return True

def _stop_sniffer():
    proc = subprocess.Popen(["pkill", "-INT", "tcpdump"], stdout=subprocess.PIPE)
    proc.wait()
    logger.info('Packet capture stopped')
    return True


if __name__ == '__main__':

    # init logging to stnd output and log files
    logger = initialize_logger(LOGDIR, COMPONENT_ID)

    # generate dirs
    for d in TMPDIR, DATADIR, LOGDIR:
        try:
            os.makedirs(d)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    ### SETUPING UP CONNECTION ###

    try:

        logger.info('Env vars imported for AMQP connection: %s , %s, %s, %s'
                    %(AMQP_VHOST,AMQP_SERVER,AMQP_USER,AMQP_PASS))
        logger.info('Setting up AMQP connection..')
        # setup AMQP connection
        credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASS)
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=AMQP_SERVER,
            virtual_host=AMQP_VHOST,
            credentials=credentials))

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
        body=json.dumps({'message': '%s is up!'%COMPONENT_ID,"_type": 'sniffing.info'}),
        exchange=AMQP_EXCHANGE,
        routing_key='control.sniffing.info',
        properties=pika.BasicProperties(
            content_type='application/json',
        )
    )

    print(" [x] Awaiting AMQP requests on topic: control.sniffing.service")
    channel.start_consuming()

