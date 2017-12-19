#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import errno
import argparse
import os
import sys
import pika
import signal
import logging
import traceback
import multiprocessing
from datetime import time

from ioppytest import TMPDIR, DATADIR, LOGDIR, AMQP_EXCHANGE, AMQP_URL
from ioppytest.utils.amqp_synch_call import publish_message
from ioppytest.utils.pure_pcapy import DLT_RAW, DLT_IEEE802_15_4_NOFCS
from ioppytest.utils.messages import *
from ioppytest.sniffer.packet_dumper import AmqpDataPacketDumper
from ioppytest.utils.rmq_handler import RabbitMQHandler, JsonFormatter


# component identification & bus params
COMPONENT_ID = '%s|%s' % ('packet_sniffer', 'amqp_connector')

# init logging to stnd output and log files
logger = logging.getLogger(COMPONENT_ID)
logger.setLevel(logging.INFO)

logging.getLogger('pika').setLevel(logging.WARNING)

# AMQP log handler with f-interop's json formatter
rabbitmq_handler = RabbitMQHandler(AMQP_URL, COMPONENT_ID)
json_formatter = JsonFormatter()
rabbitmq_handler.setFormatter(json_formatter)
logger.addHandler(rabbitmq_handler)

# in seconds
TIME_WAIT_FOR_COMPONENTS_FINISH_EXECUTION = 2
DEFAULT_TOPICS = ['#.fromAgent.#', 'control.sniffing.service']

# Global scope var
last_capture_name = None
connection = None
pcap_dumper = None
process = None
traffic_dlt = None


def main():

    global traffic_dlt

    # generate dirs
    for d in TMPDIR, DATADIR, LOGDIR:
        try:
            os.makedirs(d)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    # connection setup
    global connection

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", help="", choices=['ipv6_tun', '802_15_4_tun'])
    args = parser.parse_args()
    mode = args.mode
    
    if mode == 'ipv6_tun':
        traffic_dlt = DLT_RAW
    elif mode == '802_15_4_tun':
        traffic_dlt = DLT_IEEE802_15_4_NOFCS
    else:
        logger.error(' Unknown mode %s' % mode)
        return

    try:

        logger.info('Setting up AMQP connection..')

        # setup AMQP connection
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        channel = connection.channel()
        channel.queue_declare(queue='services_queue@%s' % COMPONENT_ID, auto_delete=True)
        channel.queue_bind(exchange=AMQP_EXCHANGE,
                           queue='services_queue@%s' % COMPONENT_ID,
                           routing_key='control.sniffing.service')

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(on_request, queue='services_queue@%s' % COMPONENT_ID)

    except pika.exceptions.ConnectionClosed as cc:
        logger.error(' AMQP cannot be established, is message broker up? \n More: %s' % traceback.format_exc())
        sys.exit(1)

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
        logger.info('SIGINT detected')
    except Exception as e:
        logger.error(' Unexpected error \n More: %s' % traceback.format_exc())
        sys.exit(1)
    finally:
        # close AMQP connection
        if connection:
            connection.close()


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
    global process
    global pcap_dumper
    global traffic_dlt

    logger.info('Identifying request...')

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
        logger.info(str(e))
        return

    if isinstance(request, MsgSniffingGetCaptureLast):
        logger.debug('Processing request: %s' % repr(request))

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
                    connection,
                    MsgErrorReply(request, error_message=str(fne))
                )
                logger.info(str(fne))
                return

            except Exception as e:
                publish_message(
                    connection,
                    MsgErrorReply(request, error_message=str(e))
                )
                logger.info(str(e))
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
                logging.warning(err_mess)
                return

            logger.info("Response ready, PCAP bytes: \n" + repr(response))
            logger.info("Sending response through AMQP interface ...")
            publish_message(connection, response)

        else:
            err_mess = 'No previous capture found.'
            m_resp = MsgErrorReply(request, error_message=err_mess)
            publish_message(connection, m_resp)
            logging.warning(err_mess)
            return

    elif isinstance(request, MsgSniffingGetCapture):

        logger.debug('Processing request: %s' % repr(request))

        try:
            capture_id = request.capture_id
            filename = "{0}.pcap".format(capture_id)
            full_path = os.path.join(TMPDIR, filename)

            # check if the size of PCAP is not zero
            if os.path.getsize(full_path) == 0:
                # raise SnifferError(message='Problem encountered with the requested PCAP')
                logger.error('Problem encountered with the requested PCAP')
                return

        except FileNotFoundError as fne:
            logging.warning('Coulnt retrieve file %s from dir' % capture_id)
            logging.warning(str(fne))
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
        with open(full_path, "rb") as file:
            enc = base64.b64encode(file.read())

        response = MsgSniffingGetCaptureReply(
            request,
            ok=True,
            filename="{0}.pcap".format(capture_id),
            value=enc.decode("utf-8")

        )

        logger.info("Response ready, PCAP bytes: \n" + repr(response))
        publish_message(connection, response)
        return

    elif isinstance(request, MsgSniffingStart):
        logger.debug('Processing request: %s' % repr(request))
        try:
            capture_id = request.capture_id
            filename = "{0}.pcap".format(capture_id)
            full_path = os.path.join(TMPDIR, filename)
        except:
            err_mess = 'No capture id provided'
            m_resp = MsgErrorReply(request, error_message=err_mess)
            publish_message(connection, m_resp)
            logger.info(err_mess)
            return

        try:
            # start process for sniffing packets
            if process is not None:
                m = "Sniffer process is already running, please stop before if you meant to restart it"
                response = MsgErrorReply(request, ok=False,error_message=m)
                logger.info(m)

            else:
                process = multiprocessing.Process(
                    target=launch_amqp_data_to_pcap_dumper,
                    name='process_%s_%s' % (COMPONENT_ID, capture_id),
                    args=(TMPDIR, filename, traffic_dlt, AMQP_URL, AMQP_EXCHANGE, DEFAULT_TOPICS))

                process.start()
                logger.info("Sniffer process started %s, pid %s" % (process,process.pid))
                response = MsgReply(request, ok=True)

        except:
            logger.error('Didnt succeed starting the sniffer process')

        last_capture_name = capture_id  # keep track of the undergoing capture name

        # send reponse to API call
        publish_message(connection, response)

    elif isinstance(request, MsgSniffingStop):

        if process is None:
            logger.info("Sniffer process not running")
            response = MsgReply(request, ok=True)
        else:
            try:  # the process stops on it's own, we just verify it is stopped
                time.sleep(TIME_WAIT_FOR_COMPONENTS_FINISH_EXECUTION)  # to avoid race conditions

                if process.is_alive():
                    response = MsgReply(request, ok=False)
                    logger.info("Sniffer process couldnt be stopped")
                else:
                    response = MsgReply(request, ok=True)
                    logger.info("Sniffer process stopped correctly")
                    process = None

            except:
                m="Sniffer process couldnt be stopped"
                logger.error(m)
                response = MsgErrorReply(request, ok=False, error_message=m)

        # send final response to API call
        publish_message(connection, response)

    else:
        logging.warning('Ignoring unrecognised service request: %s' % repr(request))


def launch_amqp_data_to_pcap_dumper(dump_dir, filename, dlt, amqp_url, amqp_exchange, topics):
    global pcap_dumper

    def signal_int_handler(self, frame):
        logger.info('got SIGINT, stopping sniffer..')

        if pcap_dumper is not None:
            pcap_dumper.stop()

    signal.signal(signal.SIGINT, signal_int_handler)

    # init pcap_dumper
    pcap_dumper = AmqpDataPacketDumper(
        dump_dir=dump_dir,
        filename=filename,
        dlt=dlt,
        amqp_url=amqp_url,
        amqp_exchange=amqp_exchange,
        topics=topics
    )

    # start pcap_dumper
    pcap_dumper.run()


if __name__ == '__main__':
    # _launch_sniffer(filename='test.pcap',filter_if='NonExistentInterface',filter_proto='')
    # _launch_sniffer(filename='test.pcap', filter_if='tun0', filter_proto='')
    main()
