#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import errno
import logging
import multiprocessing
import os
import shutil
import signal
import sys
import traceback
from datetime import time, datetime
from urllib.parse import urlparse

import pika
from amqp import Message

from ioppytest import TMPDIR, DATADIR, LOGDIR, AMQP_EXCHANGE, AMQP_URL
from ioppytest.utils.amqp_synch_call import publish_message
from ioppytest.utils.messages import *
from ioppytest.utils.pure_pcapy import DLT_RAW, DLT_IEEE802_15_4_NOFCS, Dumper, Pkthdr
from ioppytest.utils.rmq_handler import RabbitMQHandler, JsonFormatter

VERSION = '0.0.2'
# -----------------
# -----------------
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
TIME_WAIT_FOR_TCPDUMP_STARTUP = 5
TIME_WAIT_FOR_COMPONENTS_FINISH_EXECUTION = 2


#Global scope var
connection = None
pcap_dumper = None
process = None


def main():
    # generate dirs
    for d in TMPDIR, DATADIR, LOGDIR:
        try:
            os.makedirs(d)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    # connection setup

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


class AmqpDataPacketDumper:
    """
    Sniffs data.serial and dumps into pcap file (assumes that frames are DLT_IEEE802_15_4)
    Sniffs data.tun and dumps into pcap file (assumes that frames are DLT_RAW)

    about pcap header:
        ts_sec: the date and time when this packet was captured. This value is in seconds since January 1,
            1970 00:00:00 GMT; this is also known as a UN*X time_t. You can use the ANSI C time() function
            from time.h to get this value, but you might use a more optimized way to get this timestamp value.
            If this timestamp isn't based on GMT (UTC), use thiszone from the global header for adjustments.

        ts_usec: in regular pcap files, the microseconds when this packet was captured, as an offset to ts_sec.
            In nanosecond-resolution files, this is, instead, the nanoseconds when the packet was captured, as
            an offset to ts_sec
            /!\ Beware: this value shouldn't reach 1 second (in regular pcap files 1 000 000;
            in nanosecond-resolution files, 1 000 000 000); in this case ts_sec must be increased instead!

        incl_len: the number of bytes of packet data actually captured and saved in the file. This value should
            never become larger than orig_len or the snaplen value of the global header.

        orig_len: the length of the packet as it appeared on the network when it was captured. If incl_len and
            orig_len differ, the actually saved packet size was limited by snaplen.
    """
    COMPONENT_ID = '6Lowpan_capture_dumper_%s' % uuid.uuid1()  # uuid in case several dumpers listening to bus
    DEFAULT_DUMP_DIR = TMPDIR
    DEFAULT_FILENAME = "test.pcap"

    DEFAULT_RAWIP_DUMP_FILENAME = "DLT_RAW.pcap"
    DEFAULT_802154_DUMP_FILENAME = "DLT_IEEE802_15_4_NO_FCS.pcap"
    NETWORK_DUMPS = [DEFAULT_802154_DUMP_FILENAME, DEFAULT_RAWIP_DUMP_FILENAME]

    DEFAULT_RAWIP_DUMP_FILENAME_WR = "DLT_RAW.pcap~"
    DEFAULT_802154_DUMP_FILENAME_WR = "DLT_IEEE802_15_4_NO_FCS.pcap~"
    NETWORK_DUMPS_TEMP = [DEFAULT_RAWIP_DUMP_FILENAME_WR, DEFAULT_802154_DUMP_FILENAME_WR]

    QUANTITY_MESSAGES_PER_PCAP = 100

    def __init__(self, dump_dir, filename, amqp_url=None, amqp_exchange=None, topics=None):
        self.messages_dumped = 0
        self.url = amqp_url
        self.exchange = amqp_exchange

        if dump_dir:
            self.dump_dir = dump_dir
        else:
            self.dump_dir = self.DEFAULT_DUMP_DIR

        if filename:
            self.filename = filename
        else:
            self.filename = self.DEFAULT_FILENAME

        if not os.path.exists(self.dump_dir):
            os.makedirs(self.dump_dir)

        # pcap dumpers
        self.pcap_15_4_dumper = None
        self.pcap_raw_ip_dumper = None
        self.dumpers_init()

        # AMQP stuff
        self.connection = pika.BlockingConnection(pika.URLParameters(self.url))  # queues & default exchange declaration
        self.channel = self.connection.channel()

        self.data_queue_name = 'data@%s' % self.COMPONENT_ID
        self.channel.queue_declare(queue=self.data_queue_name,
                                   auto_delete=True,
                                   arguments={'x-max-length': 1000}
                                   )

        # subscribe to data plane channels
        for t in topics:
            self.channel.queue_bind(exchange=self.exchange,
                                    queue=self.data_queue_name,
                                    routing_key=t)

        # subscribe to channel where the terminate session message is published
        self.channel.queue_bind(exchange=self.exchange,
                                queue=self.data_queue_name,
                                routing_key='control.session')

        # publish Hello message in bus
        self.channel.basic_publish(
            body=json.dumps({'_type': '%s.info' % self.COMPONENT_ID,
                             'value': '%s is up!' % self.COMPONENT_ID, }
                            ),
            routing_key='control.%s.info' % self.COMPONENT_ID,
            exchange=self.exchange,
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.on_request, queue=self.data_queue_name)

    def dumpers_init(self):
        # delete existing default pcap files
        for net_dump_filename in self.NETWORK_DUMPS_TEMP:
            full_path = os.path.join(self.dump_dir, net_dump_filename)
            if os.path.exists(full_path):
                if os.path.isfile(full_path):
                    os.remove(full_path)

        self.pcap_15_4_dumper = Dumper(
            filename=os.path.join(self.dump_dir, self.filename),
            snaplen=200,
            network=DLT_IEEE802_15_4_NOFCS
        )

        self.pcap_raw_ip_dumper = Dumper(
            filename=os.path.join(self.dump_dir, self.DEFAULT_RAWIP_DUMP_FILENAME_WR),
            snaplen=200,
            network=DLT_RAW
        )

    def dump_packet(self, message):

        try:
            t = time.time()
            t_s = int(t)
            t_u_delta = int((t - t_s) * 1000000)
            if 'serial' in message.interface_name:
                raw_packet = bytes(message.data)
                packet_slip = bytes(message.data_slip)

                # lets build pcap header for packet
                pcap_packet_header = Pkthdr(
                    ts_sec=t_s,
                    ts_usec=t_u_delta,
                    incl_len=len(raw_packet),
                    orig_len=len(raw_packet),
                )

                self.pcap_15_4_dumper.dump(pcap_packet_header, raw_packet)

                self.messages_dumped += 1

                shutil.copyfile(
                    os.path.join(self.dump_dir, self.filename),
                    os.path.join(self.dump_dir, self.DEFAULT_802154_DUMP_FILENAME)
                )

            elif 'tun' in message.interface_name:
                raw_packet = bytes(message.data)

                # lets build pcap header for packet
                pcap_packet_header = Pkthdr(
                    ts_sec=t_s,
                    ts_usec=t_u_delta,
                    incl_len=len(raw_packet),
                    orig_len=len(raw_packet),
                )

                self.pcap_raw_ip_dumper.dump(pcap_packet_header, raw_packet)

                self.messages_dumped += 1

                shutil.copyfile(
                    os.path.join(self.dump_dir, self.DEFAULT_RAWIP_DUMP_FILENAME_WR),
                    os.path.join(self.dump_dir, self.DEFAULT_RAWIP_DUMP_FILENAME)
                )

            else:
                logger.info('Raw packet not dumped to pcap: ' + repr(message))
                return

        except Exception as e:
            logger.error(e)

        print("Messages dumped : " + str(self.messages_dumped))

    def dumps_rotate(self):
        for net_dump_filename in self.NETWORK_DUMPS:
            full_path = os.path.join(self.dump_dir, net_dump_filename)
            if os.path.isfile(full_path):
                logger.info('rotating file dump: %s' % full_path)
                shutil.copyfile(
                    full_path,
                    os.path.join(self.dump_dir, datetime.now().strftime('%Y%m%d_%H%M%S_') + net_dump_filename),
                )

    def stop(self):
        logger.info("Stopping sniffer...")
        self.channel.queue_delete(self.data_queue_name)
        self.channel.stop_consuming()
        self.connection.close()

    def on_request(self, ch, method, props, body):
        ch.basic_ack(delivery_tag=method.delivery_tag)

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

            m = Message.from_json(body)
            m.update_properties(**props_dict)
            logger.info('got event: %s' % type(m))

            if isinstance(m, MsgTestingToolTerminate):
                ch.stop_consuming()
                self.stop()
                logger.info('Sniffer stopped...')
                

            if isinstance(m, MsgPacketSniffedRaw):

                self.dump_packet(m)

                try:  # rotate files each X messages dumped
                    if self.messages_dumped != 0 and self.messages_dumped % self.QUANTITY_MESSAGES_PER_PCAP == 0:
                        self.dumps_rotate()
                        self.dumpers_init()

                except Exception as e:
                    logger.error(e)

            else:
                logger.info('drop amqp message: ' + repr(m))

        except NonCompliantMessageFormatError as e:
            print('* * * * * * API VALIDATION ERROR * * * * * * * ')
            print("AMQP MESSAGE LIBRARY COULD PROCESS JSON MESSAGE")
            print('* * * * * * * * * * * * * * * * * * * * * * * * *  \n')
            # raise NonCompliantMessageFormatError("AMQP MESSAGE LIBRARY COULD PROCESS JSON MESSAGE")

        except Exception as e:
            logger.error(e)
            req_body_dict = json.loads(body.decode('utf-8'), object_pairs_hook=OrderedDict)
            logger.error("Message: %s, body: %s" % (json.dumps(req_body_dict), str(body)))

    def run(self):
        print("Starting thread listening on the event bus")
        self.channel.start_consuming()
        print('Bye byes!')


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
                    connection,
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

        filename = "{0}/{1}.pcap".format(TMPDIR, capture_id)

        try:
            # start process for sniffing packets
            logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

            if process is not None:
                process.terminate()
                print("TERMINATE PROCESS")
            process = multiprocessing.Process(target=launch_amqp_data_to_pcap_dumper, args=(TMPDIR, filename))
            process.start()
            print("START et %s" % process)


        except:
            logger.error('Didnt succeed starting the capture')

        last_capture_name = capture_id  # keep track of the undergoing capture name
        time.sleep(TIME_WAIT_FOR_TCPDUMP_STARTUP)  # to avoid race conditions
        response = MsgReply(request, ok=True)
        publish_message(connection, response)

    elif isinstance(request, MsgSniffingStop):

        try:
            time.sleep(TIME_WAIT_FOR_COMPONENTS_FINISH_EXECUTION)  # to avoid race conditions
            # _stop_sniffer()

            if process is not None:
                print("Process terminated")
                process.terminate()
        except:
            logger.error('Didnt succeed stopping the sniffer')

        response = MsgReply(request, ok=True)
        publish_message(connection, response)

    else:
        logger.warning('Ignoring unrecognised service request: %s' % repr(request))


def launch_amqp_data_to_pcap_dumper(dump_dir= None, filename = None, amqp_url=None, amqp_exchange=None, topics=None):
    
    global pcap_dumper

    def signal_int_handler(self, frame):
        logger.info('got SIGINT, stopping sniffer..')

        if pcap_dumper is not None:
            pcap_dumper.stop()

    signal.signal(signal.SIGINT, signal_int_handler)

    if amqp_url and amqp_exchange:
        amqp_exchange = amqp_exchange
        amqp_url = amqp_url

    else:
        try:
            amqp_exchange = str(os.environ['AMQP_EXCHANGE'])
            print('Imported AMQP_EXCHANGE env var: %s' % amqp_exchange)
        except KeyError as e:
            amqp_exchange = "amq.topic"
            print('Cannot retrieve environment variables for AMQP EXCHANGE. Loading default: %s' % amqp_exchange)
        try:
            amqp_url = str(os.environ['AMQP_URL'])
            print('Imported AMQP_URL env var: %s' % amqp_url)
            p = urlparse(amqp_url)
            user = p.username
            server = p.hostname
            logger.info(
                "Env variables imported for AMQP connection, User: {0} @ Server: {1} ".format(user,
                                                                                              server))
        except KeyError:
            print('Cannot retrieve environment variables for AMQP connection. Loading defaults..')
            # load default values
            amqp_url = "amqp://{0}:{1}@{2}/{3}".format("guest", "guest", "localhost", "/")

    if topics:
        print("Imported Topics")
        pcap_amqp_topic_subscriptions = topics
    else:
        print("Default Topics")
        pcap_amqp_topic_subscriptions = ['data.tun.fromAgent.*',
                                         'data.serial.fromAgent.*']

    # init pcap_dumper
    pcap_dumper = AmqpDataPacketDumper(
        dump_dir=dump_dir,
        filename=filename,
        amqp_url=amqp_url,
        amqp_exchange=amqp_exchange,
        topics=pcap_amqp_topic_subscriptions
    )
    # start pcap_dumper
    pcap_dumper.run()


if __name__ == '__main__':
        # _launch_sniffer(filename='test.pcap',filter_if='NonExistentInterface',filter_proto='')
        # _launch_sniffer(filename='test.pcap', filter_if='tun0', filter_proto='')
        main()
