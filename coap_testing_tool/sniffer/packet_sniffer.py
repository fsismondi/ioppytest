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
from coap_testing_tool.utils.amqp_synch_call import publish_message
from coap_testing_tool import TMPDIR, DATADIR, LOGDIR, AMQP_EXCHANGE, AMQP_URL
from coap_testing_tool.utils.rmq_handler import RabbitMQHandler, JsonFormatter
from coap_testing_tool.utils.event_bus_messages import *

COMPONENT_ID = 'packet_sniffer'
last_capture_name = None

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)

logging.getLogger('pika').setLevel(logging.INFO)

# init logging to stnd output and log files
logger = logging.getLogger(COMPONENT_ID)

# default handler
sh = logging.StreamHandler()
logger.addHandler(sh)

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)
logger.setLevel(logging.DEBUG)

# in seconds
TIME_WAIT_FOR_TCPDUMP_ON = 5
TIME_WAIT_FOR_COMPONENTS_FINISH_EXECUTION = 2

connection = None

def on_request(ch, method, props, body):
    """

    :param ch:
    :param method:
    :param props:
    :param body:
    :return:
    """
    # ack message received
    ch.basic_ack(delivery_tag=method.delivery_tag)

    global last_capture_name
    global connection

    try:
        props_dict = {
            'content_type': props.content_type,
            'delivery_mode': props.delivery_mode,
            'correlation_id': props.correlation_id,
            'reply_to': props.reply_to,
            'message_id': props.message_id,
            'timestamp': props.timestamp,
            'user_id': props.user_id,
            'app_id': props.app_id,
        }
        request = Message.from_json(body)
        request.update_properties(**props_dict)

    except Exception as e:
        logger.error(str(e))
        return

    if isinstance(request, MsgSniffingGetCaptureLast):
        logger.info('Processing request: %s' % repr(request))

        if last_capture_name:
            capture_id = last_capture_name

            try:
                file = TMPDIR + '/%s.pcap' % capture_id
                # check if the size of PCAP is not zero
                if os.path.getsize(file) == 0:
                    # raise SnifferError(message='Problem encountered with the requested PCAP')
                    logger.error('Problem encountered with the requested PCAP')
                    return

            except FileNotFoundError as fne:
                publish_message(
                    ch,
                    MsgErrorReply(request, error_message=str(fne))
                )
                logger.error(str(fne))
                return

            except Exception as e:
                publish_message(
                    connection,
                    MsgErrorReply(request, error_message=str(e))
                )
                logger.error(str(e))
                return

            logger.info("Encoding PCAP file into base64 ...")

            try:
                # do not dump into PCAP_DIR, coordinator puts the PCAPS there
                with open(TMPDIR + "/%s.pcap" % capture_id, "rb") as file:
                    enc = base64.b64encode(file.read())

                response = MsgSniffingGetCaptureLastReply(
                    request,
                    ok=True,
                    filename='%s.pcap' % capture_id,
                    value=enc.decode("utf-8")
                )
            except Exception as e:
                err_mess = str(e)
                m_resp = MsgErrorReply(request, error_message=err_mess)
                publish_message(connection, m_resp)
                logger.warning(err_mess)
                return

            logger.info("Response ready, PCAP bytes: \n" + repr(response))
            logger.info("Sending response through AMQP interface ...")
            publish_message(connection, response)

        else:
            err_mess = 'No previous capture found.'
            m_resp = MsgErrorReply(request, error_message=err_mess)
            publish_message(connection, m_resp)
            logger.warning(err_mess)
            return

    elif isinstance(request, MsgSniffingGetCapture):

        logger.info('Processing request: %s' % repr(request))

        try:
            capture_id = request.capture_id
            file = TMPDIR + '/%s.pcap' % capture_id

            # check if the size of PCAP is not zero
            if os.path.getsize(file) == 0:
                # raise SnifferError(message='Problem encountered with the requested PCAP')
                logger.error('Problem encountered with the requested PCAP')
                return

        except FileNotFoundError as fne:
            logger.warning('Coulnt retrieve file %s from dir' % file)
            logger.warning(str(fne))
            publish_message(
                connection,
                MsgErrorReply(
                    request,
                    error_message=str(fne)
                )
            )
            return

        logger.info("Encoding PCAP file into base64 ...")

        # do not dump into PCAP_DIR, coordinator puts the PCAPS there
        with open(TMPDIR + "/%s.pcap" % capture_id, "rb") as file:
            enc = base64.b64encode(file.read())

        response = MsgSniffingGetCaptureReply(
            request,
            ok=True,
            filename='%s.pcap' % capture_id,
            value=enc.decode("utf-8")

        )

        logger.info("Response ready, PCAP bytes: \n" + repr(response))
        logger.info("Sending response through AMQP interface ...")
        publish_message(connection, response)
        return

    elif isinstance(request, MsgSniffingStart):
        logger.info('Processing request: %s' % repr(request))
        try:
            capture_id = request.capture_id
        except:
            err_mess = 'No capture id provided'
            m_resp = MsgErrorReply(request, error_message=err_mess)
            publish_message(connection, m_resp)
            logger.error(err_mess)
            return

        filename = TMPDIR + '/' + capture_id + ".pcap"
        filter_if = ''

        try:
            filter_if = request.filter_if
        except:
            logger.warning('No interface (filter_if) name provided')

        try:
            filter_proto = request.filter_proto
        except:
            logger.warning('No filter_proto provided')

        try:
            _launch_sniffer(filename, filter_if, filter_proto)
        except:
            logger.error('Didnt succeed starting the capture')

        last_capture_name = capture_id  # keep track of the undergoing capture name
        time.sleep(TIME_WAIT_FOR_TCPDUMP_ON)  # to avoid race conditions
        response = MsgReply(request)  # by default sends ok = True
        publish_message(connection, response)

    elif isinstance(request, MsgSniffingStop):

        logger.info('Processing request: %s' % repr(request))

        try:
            time.sleep(TIME_WAIT_FOR_COMPONENTS_FINISH_EXECUTION)  # to avoid race conditions
            _stop_sniffer()
        except:
            logger.error('Didnt succeed stopping the sniffer')

        response = MsgReply(request)  # by default sends ok = True
        publish_message(connection, response)

    else:
        logger.warning('Ignoring unrecognised service request: %s' % repr(request))


### IMPLEMENTATION OF SERVICES ###

def _launch_sniffer(filename, filter_if, filter_proto):
    """

    :param filename:
    :param filter_if:
    :param filter_proto:
    :return:
    """
    logger.info('Launching packet capture..')

    sys_type = platform.system()

    if filter_proto is None:
        filter_proto = 'udp'  # for CoAP over TCP not yet supported

    if (filter_if is None) or (filter_if == ''):
        if sys_type == 'Darwin':
            filter_if = 'lo0'
        else:
            filter_if = 'lo'
            # TODO windows?

    # lets try to remove the file in case there's a previous execution of the TC
    try:
        cmd = 'rm ' + filename
        proc_rm = subprocess.Popen(cmd, stderr=subprocess.PIPE, shell=True)
        # output = str(proc_rm.stderr.readline())
        # logging.info('process stdout: %s' % output)
    except:
        pass

    if sys_type == 'Darwin':  # macos port of tcpdump bugs when using -U  option and filters :/
        cmd = 'tcpdump -K -i ' + filter_if + ' -s 200 ' + ' -w ' + filename
    else:
        cmd = 'tcpdump -K -i ' + filter_if + ' -s 200 ' + ' -U -w ' + filename + ' ' + filter_proto

    logger.info('spawning process with : %s' % str(cmd))

    proc_sniff = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    logger.info('process stderr: %s' % str(proc_sniff.stderr.readline()))
    # logger.info('process stdout: %s' % str(proc_sniff.stdout.readline()))

    return True


def _stop_sniffer():
    proc = subprocess.Popen(["pkill", "-INT", "tcpdump"], stdout=subprocess.PIPE)
    proc.wait()
    logger.info('Packet capture stopped')
    return True


def main():
    # generate dirs
    for d in TMPDIR, DATADIR, LOGDIR:
        try:
            os.makedirs(d)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    ### SETUPING UP CONNECTION ###

    global connection

    try:

        logger.info('Setting up AMQP connection..')

        # setup AMQP connection
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        channel = connection.channel()

        channel.queue_declare(queue='services_queue@%s' % COMPONENT_ID, auto_delete=True)

        channel.queue_bind(exchange=AMQP_EXCHANGE,
                           queue='services_queue@%s' % COMPONENT_ID,
                           routing_key='control.sniffing.service')

    except pika.exceptions.ConnectionClosed as cc:
        logger.error(' AMQP cannot be established, is message broker up? \n More: %s' % traceback.format_exc())
        sys.exit(1)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(on_request, queue='services_queue@%s' % COMPONENT_ID)

    msg = MsgTestingToolComponentReady(
        component='sniffing'
    )

    publish_message(connection, msg)

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
        # close AMQP connection
        if connection:
            connection.close()


if __name__ == '__main__':
    # _launch_sniffer(filename='test.pcap',filter_if='NonExistentInterface',filter_proto='')
    # _launch_sniffer(filename='test.pcap', filter_if='tun0', filter_proto='')
    main()
