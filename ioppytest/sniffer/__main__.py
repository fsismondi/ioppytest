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

from ioppytest import TMPDIR, DATADIR, LOGDIR, AMQP_URL, AMQP_EXCHANGE, LOG_LEVEL
from ioppytest.utils.amqp_synch_call import publish_message
from ioppytest.utils.pure_pcapy import DLT_RAW, DLT_IEEE802_15_4_NOFCS
from ioppytest.utils.messages import *
from ioppytest.sniffer.packet_dumper import AmqpDataPacketDumper
from ioppytest.utils.rmq_handler import RabbitMQHandler, JsonFormatter

logging.getLogger('pika').setLevel(logging.WARNING)

# in seconds
TIME_WAIT_FOR_COMPONENTS_FINISH_EXECUTION = 2

# generate dirs
for d in TMPDIR, DATADIR, LOGDIR:
    try:
        os.makedirs(d)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


class Sniffer:
    DEFAULT_TOPICS = ['#.fromAgent.#', 'control.sniffing.service']

    def __init__(self, traffic_dlt, amqp_url, amqp_exchange):
        self.traffic_dlt = traffic_dlt
        self.last_capture_name = None
        self.pcap_dumper_subprocess = None
        self.connection = None

        self.exchange = amqp_exchange
        self.url = amqp_url

        # component identification & bus params
        self.COMPONENT_ID = '%s|%s' % ('packet_sniffer', 'amqp_connector')

        # init logging to stnd output and log files
        self.logger = logging.getLogger(self.COMPONENT_ID)
        self.logger.setLevel(LOG_LEVEL)

    def connect(self):

        # AMQP log handler with f-interop's json formatter
        rabbitmq_handler = RabbitMQHandler(self.url, self.COMPONENT_ID)
        json_formatter = JsonFormatter()
        rabbitmq_handler.setFormatter(json_formatter)
        self.logger.addHandler(rabbitmq_handler)

        try:
            self.logger.info('Setting up AMQP connection..')

            # setup AMQP connection
            self.connection = pika.BlockingConnection(pika.URLParameters(self.url))
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue='services_queue@%s' % self.COMPONENT_ID, auto_delete=True)

            for t in self.DEFAULT_TOPICS:
                self.channel.queue_bind(exchange=self.exchange,
                                        queue='services_queue@%s' % self.COMPONENT_ID,
                                        routing_key=t)

                self.channel.basic_qos(prefetch_count=1)
                self.channel.basic_consume(self.on_request, queue='services_queue@%s' % self.COMPONENT_ID)

        except pika.exceptions.ConnectionClosed:
            self.logger.error(' AMQP cannot be established, is message broker up? \n More: %s' % traceback.format_exc())
            sys.exit(1)

    def on_request(self, ch, method, props, body):
        # ack message received
        ch.basic_ack(delivery_tag=method.delivery_tag)

        self.logger.info('Identifying request...')

        try:
            request = Message.load_from_pika(method, props, body)
        except Exception as e:
            self.logger.info(str(e))
            return

        if isinstance(request, MsgSniffingGetCaptureLast):
            self.logger.debug('Processing request: %s' % repr(request))

            if self.last_capture_name:
                capture_id = self.last_capture_name

                try:
                    file = TMPDIR + '/%s.pcap' % capture_id
                    # check if the size of PCAP is not zero
                    if os.path.getsize(file) == 0:
                        # raise SnifferError(message='Problem encountered with the requested PCAP')
                        self.logger.error('Problem encountered with the requested PCAP')
                        return

                except FileNotFoundError as fne:
                    publish_message(
                        self.connection,
                        MsgErrorReply(request, error_message=str(fne))
                    )
                    self.logger.info(str(fne))
                    return

                except Exception as e:
                    publish_message(
                        self.connection,
                        MsgErrorReply(request, error_message=str(e))
                    )
                    self.logger.info(str(e))
                    return

                self.logger.info("Encoding PCAP file into base64 ...")

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
                    publish_message(self.connection, m_resp)
                    logging.warning(err_mess)
                    return

                self.logger.info("Response ready, PCAP bytes: \n" + repr(response))
                self.logger.info("Sending response through AMQP interface ...")
                publish_message(self.connection, response)

            else:
                err_mess = 'No previous capture found.'
                m_resp = MsgErrorReply(request, error_message=err_mess)
                publish_message(self.connection, m_resp)
                logging.warning(err_mess)
                return

        elif isinstance(request, MsgSniffingGetCapture):

            self.logger.debug('Processing request: %s' % repr(request))

            try:
                capture_id = request.capture_id
                filename = "{0}.pcap".format(capture_id)
                full_path = os.path.join(TMPDIR, filename)

                # check if the size of PCAP is not zero
                if os.path.getsize(full_path) == 0:
                    # raise SnifferError(message='Problem encountered with the requested PCAP')
                    self.logger.error('Problem encountered with the requested PCAP')
                    return

            except FileNotFoundError as fne:
                logging.warning('Coulnt retrieve file %s from dir' % capture_id)
                logging.warning(str(fne))
                publish_message(
                    self.connection,
                    MsgErrorReply(
                        request,
                        error_message=str(fne)
                    )
                )
                return

            self.logger.info("Encoding PCAP file into base64 ...")

            # do not dump into PCAP_DIR, coordinator puts the PCAPS there
            with open(full_path, "rb") as file:
                enc = base64.b64encode(file.read())

            response = MsgSniffingGetCaptureReply(
                request,
                ok=True,
                filename="{0}.pcap".format(capture_id),
                value=enc.decode("utf-8")

            )

            self.logger.info("Response ready, PCAP bytes: \n" + repr(response))
            publish_message(self.connection, response)
            return

        elif isinstance(request, MsgSniffingStart):
            self.logger.debug('Processing request: %s' % repr(request))
            try:
                capture_id = request.capture_id
                filename = "{0}.pcap".format(capture_id)
                full_path = os.path.join(TMPDIR, filename)
            except:
                err_mess = 'No capture id provided'
                m_resp = MsgErrorReply(request, error_message=err_mess)
                publish_message(self.connection, m_resp)
                self.logger.info(err_mess)
                return

            try:
                # start process for sniffing packets
                if self.pcap_dumper_subprocess is not None:
                    m = "Sniffer process is already running, please stop before if you meant to restart it"
                    response = MsgErrorReply(request, ok=False, error_message=m)
                    self.logger.info(m)

                else:
                    self.pcap_dumper_subprocess = multiprocessing.Process(
                        target=launch_amqp_data_to_pcap_dumper,
                        name='process_%s_%s' % (self.COMPONENT_ID, capture_id),
                        args=(TMPDIR, filename, self.traffic_dlt, self.url, self.exchange, self.DEFAULT_TOPICS))

                    self.pcap_dumper_subprocess.start()
                    self.logger.info("Sniffer process started %s, pid %s" % (
                        self.pcap_dumper_subprocess, self.pcap_dumper_subprocess.pid))
                    response = MsgReply(request, ok=True)

            except Exception as e:
                m = 'Didnt succeed starting the sniffer process, the exception captured is %s'%str(e)
                self.logger.error(m)
                response = MsgErrorReply(request, ok=False, error_message=m)

            self.last_capture_name = capture_id  # keep track of the undergoing capture name

            # send reponse to API call
            publish_message(self.connection, response)

        elif isinstance(request, MsgSniffingStop):

            if self.pcap_dumper_subprocess is None:
                self.logger.info("Sniffer process not running")
                response = MsgReply(request, ok=True)
            else:
                try:  # the process stops on it's own, we just verify it is stopped
                    time.sleep(TIME_WAIT_FOR_COMPONENTS_FINISH_EXECUTION)  # to avoid race conditions

                    if self.pcap_dumper_subprocess.is_alive():
                        response = MsgReply(request, ok=False)
                        self.logger.info("Sniffer process couldnt be stopped")
                    else:
                        response = MsgReply(request, ok=True)
                        self.logger.info("Sniffer process stopped correctly")
                        self.pcap_dumper_subprocess = None

                except:
                    m = "Sniffer process couldnt be stopped"
                    self.logger.error(m)
                    response = MsgErrorReply(request, ok=False, error_message=m)

            # send final response to API call
            publish_message(self.connection, response)

        else:
            pass

    def run(self):

        self.connect()
        msg = MsgTestingToolComponentReady(component='sniffing')
        publish_message(self.connection, msg)

        try:
            self.logger.info("Awaiting AMQP requests on topic: control.sniffing.service")
            self.channel.start_consuming()
        except pika.exceptions.ConnectionClosed as cc:
            self.logger.error(' AMQP connection closed: %s' % str(cc))
            sys.exit(1)
        except KeyboardInterrupt as KI:
            self.logger.info('SIGINT detected')
        except Exception as e:
            self.logger.error(' Unexpected error \n More: %s' % traceback.format_exc())
            sys.exit(1)
        finally:
            # close AMQP connection
            if self.connection:
                self.connection.close()


def launch_amqp_data_to_pcap_dumper(dump_dir, filename, dlt, amqp_url, amqp_exchange, topics):
    def signal_int_handler(self, frame):
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

    return pcap_dumper


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", help="", choices=['ipv6_tun', '802_15_4_tun'])
    args = parser.parse_args()
    mode = args.mode

    if mode == 'ipv6_tun':
        traffic_dlt = DLT_RAW
    elif mode == '802_15_4_tun':
        traffic_dlt = DLT_IEEE802_15_4_NOFCS
    else:
        print(' Unknown mode %s' % mode)
        return

    sniffer = Sniffer(
        traffic_dlt=traffic_dlt,
        amqp_url=AMQP_URL,
        amqp_exchange=AMQP_EXCHANGE
    )

    sniffer.run()


if __name__ == '__main__':
    main()
