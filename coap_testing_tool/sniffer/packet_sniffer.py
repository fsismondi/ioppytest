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
import logging
from coap_testing_tool.utils.amqp_synch_call import amqp_reply
from coap_testing_tool.utils.logger import  initialize_logger
from coap_testing_tool import TMPDIR, DATADIR, PCAP_DIR, LOGDIR, AMQP_EXCHANGE, AMQP_USER, AMQP_SERVER, AMQP_PASS, AMQP_VHOST
from coap_testing_tool.utils.exceptions import ApiMessageFormatError, SnifferError

COMPONENT_ID = 'packet_sniffer'

ALLOWED_EXTENSIONS = set(['pcap'])

def on_request(ch, method, props, body):

    # ack message received
    ch.basic_ack(delivery_tag=method.delivery_tag)

    req_dict = json.loads(body.decode('utf-8'))

    logger.debug('[event queue callback] service request received on the queue: %s || %s'
                 % (method.routing_key, json.loads(body.decode('utf-8'), object_pairs_hook=OrderedDict)))

    try:
        req_type = req_dict['_type']

    except Exception as e:
        # TODO forward errors to event bus
        raise e

    if req_type == 'sniffing.getcapture':
        logger.info('Processing %s request'%req_type)
        try:
            capture_id = req_dict['capture_id']
        except:
            raise ApiMessageFormatError(message='No capture_id provided')

        try:
            file = PCAP_DIR+'/%s.pcap'%capture_id
        # check if the size of PCAP is not zero
            if os.path.getsize(file)== 0:
                raise SnifferError(message='Problem encountered with the requested PCAP')
        except FileNotFoundError as fne:
            logger.error('Coulnt retrieve file %s from dir'%file)
            raise
            return

        logging.info("Encoding PCAP file into base64 ...")
        with open(PCAP_DIR+"/%s.pcap"%capture_id, "rb") as file:
            enc = base64.b64encode(file.read())

        # lets build response
        response = OrderedDict()
        response.update({'_type': req_type})
        response.update({'ok': True})
        response.update({'filetype':'pcap_base64'})
        response.update({'filename':'%s.pcap'%capture_id})
        response.update({'value': enc.decode("utf-8")})

        logging.info("Response ready, PCAP bytes: \n" + str(response))
        logging.info("Sending PCAP through the AMQP interface ...")

        amqp_reply(ch, props, response)

    elif req_type == 'sniffing.start':
        logger.info('Processing %s request' % req_type)
        try:
            capture_id = req_dict['capture_id']
        except:
            raise ApiMessageFormatError(message='No capture_id provided')

        filename = PCAP_DIR + '/' + capture_id + ".pcap"

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
            raise SnifferError('Didnt succeed launching sniffer')

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
            raise SnifferError('Didnt succeed stopping sniffer')

        # lets build response
        response = OrderedDict()
        response.update({'_type': req_type})
        response.update({'ok': True})
        amqp_reply(ch, props, response)

    else:
        response = OrderedDict()
        response.update({'_type': req_type})
        response.update({'ok': False})
        response.update({'value': 'Wrong request received: %s' % str(req_dict)})

        amqp_reply(ch, props, response)
        logger.error('Wrong request received: %s' % str(req_dict))

### IMPLEMENTATION OF SERVICES ###

#sudo needed?
def _launch_sniffer(filename, filter_if, filter_proto):
    logger.info('Launching sniffer..')

    if filter_proto is None:
        filter_proto=''

    if (filter_if is None ) or (filter_if==''):
        sys_type = platform.system()
        if sys_type == 'Darwin':
            filter_if = 'lo0'
        else:
            filter_if = 'lo'
            # TODO windows?

    # when coordinator is being deployed in a VM it should provide the iterface name ex iminds-> 'eth0.29'

    # TODO re-implement with subprocess module


    # -U -w params: as each packet is saved, it will be written to the output
    #               file, rather than being written only when the output buffer
    #               fills.
    # params = ['tcpdump',
    #           '-i ' + filter_if,
    #           '-s 200',
    #           '-U -w '+ filename,
    #           filter_proto,
    #           '-vv',
    #           '&']
    #proc = subprocess.Popen(params, stdout=subprocess.PIPE)

    params = 'tcpdump -i ' + filter_if +' -s 200 ' + ' -U -w '+ filename +' '+ filter_proto + '&'
    os.system(params)

    logger.info('creating process tcpdump with: %s'%params)

    return True

def _stop_sniffer():
    proc = subprocess.Popen(["pkill", "-INT", "tcpdump"], stdout=subprocess.PIPE)
    proc.wait()
    logger.info('Sniffing stopped')
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

    print(" [x] Awaiting AMQP requests on topic: control.sniffing.service")
    channel.start_consuming()
#
#
# # DELETE:
#
# #!/usr/bin/env python3
#
# # import sys, platform
# # from os import listdir, path, walk, stat
# # import glob
# # from flask import  Flask, Response, request, abort, jsonify, send_from_directory
#
# PCAP_DIR = './data/dumps/'
# ALLOWED_EXTENSIONS = set(['pcap'])
# LAST_FILENAME="TEST"
#
# import subprocess
# import json
#
# app = Flask(__name__)
#
#
# #for the remote sniffer
# @app.route('/sniffer_api/HelloWorld', methods=['GET'])
# def get_HelloWorld():
#     return Response(json.dumps("HelloWorld"))
#
#
# #for the remote sniffer
# @app.route('/sniffer_api/launchSniffer', methods=['POST'])
# def launchSniffer():
#     testcase_id = request.args.get('testcase_id', '')
#     interface_name = request.args.get('interface', '')
#     filter = request.args.get('filter', '')
#
#     if filter is '':
#         #defaults
#         filter = 'udp port 5683'
#
#     if (interface_name is None ) or (interface_name==''):
#         sys_type = platform.system()
#         if sys_type == 'Darwin':
#             interface_name = 'lo0'
#         else:
#             interface_name = 'lo'
#         # TODO for windows?
#
#         # when coordinator is beeing deployed in a VM it should provide the iterface name ex iminds-> 'eth0.29'
#
#
#     print("-----------------")
#     print("LAUNCHING SNIFFER")
#     print("-----------------")
#
#     _launchSniffer(testcase_id,interface_name,filter)
#     return Response(json.dumps( ("sniffer","sniffing traffic for " + testcase_id + ' / ' + filter + ' / ' + interface_name)))
#
# #for the remote sniffer
# @app.route('/sniffer_api/finishSniffer', methods=['GET','POST'])
# def get_finishSniffer():
#     global LAST_FILENAME
#     print("-----------------")
#     print("TERMINATE SNIFFER")
#     print("-----------------")
#     _finishSniffer()
#     return Response(json.dumps("testcase sniffer stopped, dumped file : " + LAST_FILENAME ))
#
#
#
#
# #sudo needed?
# def _launchSniffer(testcase_id, interface_name, filter):
#     # TODO re-implement with subprocess module
#     import os
#     global LAST_FILENAME
#     LAST_FILENAME = PCAP_DIR + testcase_id + ".pcap"
#
#     # -U -w params: as each packet is saved, it will be written to the output
#     #               file, rather than being written only when the output buffer
#     #               fills.
#     cmd = "tcpdump -i " + interface_name + " -s 200 -U -w " + LAST_FILENAME +  " " + filter+ " &"
#     print("-----------------")
#     print("sniffing:  " + cmd)
#     print("-----------------")
#     os.system(cmd)
#
#
# #sudo needed?
# def _finishSniffer():
#     proc = subprocess.Popen(["pkill", "-INT", "tcpdump"], stdout=subprocess.PIPE)
#     proc.wait()
#
# #sudo needed?
# def _getSniffedPcap():
#     return LAST_FILENAME



