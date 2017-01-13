# -*- coding: utf-8 -*-
#!/usr/bin/env python3

from threading import Timer

from coap_testing_tool.test_coordinator.coordinator import *
from coap_testing_tool import AMQP_VHOST, AMQP_PASS,AMQP_SERVER,AMQP_USER, AMQP_EXCHANGE
from coap_testing_tool import DATADIR,TMPDIR,LOGDIR,TD_DIR

COMPONENT_ID = 'test_coordinator'
TT_check_list = [
    'dissection',
    'analysis',
    'sniffing',
    'testcoordination',
    'packetrouting',
    'agent_TT',
]
# time to wait for components to send for READY signal
READY_SIGNAL_TOUT = 10

# init logging to stnd output and log files
logger = initialize_logger(LOGDIR, __file__)

if __name__ == '__main__':

    # generate dirs
    for d in TMPDIR, DATADIR, LOGDIR, RESULTS_DIR, PCAP_DIR:
        try:
            os.makedirs(d)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise


    # # # setup amqp connnection # # #

    try:
        logger.info('Setting up AMQP connection..')
        # setup AMQP connection
        credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASS)
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=AMQP_SERVER,
            virtual_host=AMQP_VHOST,
            credentials = credentials))


    except pika.exceptions.ConnectionClosed as cc:
        logger.error(' AMQP cannot be established, is message broker up? \n More: %s' %traceback.format_exc())
        sys.exit(1)

    channel = connection.channel()

    #in case exchange not declared
    channel.exchange_declare(
            exchange=AMQP_EXCHANGE,
            type='topic',
            durable=True,
    )

    bootstrap_q = channel.queue_declare(queue='bootstrapping', auto_delete=True)

    channel.queue_bind(
            exchange=AMQP_EXCHANGE,
            queue='bootstrapping',
            routing_key='control.session.bootstrap',
    )

    # # # starting verification of the testing tool components # # #

    channel.basic_publish(
            body=json.dumps({'message': '%s is up!' % COMPONENT_ID, "_type": 'testcoordination.ready'}),
            exchange=AMQP_EXCHANGE,
            routing_key='control.session.bootstrap',
            properties=pika.BasicProperties(
                    content_type='application/json',
            )
    )

    def on_ready_signal( ch, method, props, body):
        ch.basic_ack(delivery_tag=method.delivery_tag)

        # we should only get messages with: ROUTING_KEY: control.session.bootstrap
        # assert this, else an exception will be risen after
        assert method.routing_key == 'control.session.bootstrap'

        event = json.loads(body.decode('utf-8'),object_pairs_hook=OrderedDict)
        signal = event['_type']

        # final signal generated by coordinator
        if signal == "testingtool.ready":
            logger.info('all signals processed')
            channel.queue_delete('bootstrapping')
            return

        for s in TT_check_list:
            if s in signal:
                TT_check_list.remove(s)
                return
                logger.info('ready signals still not received %s , from %s'%(len(TT_check_list),TT_check_list))

        logger.warning('not processed signal %s'%signal)

    # bind callback funtion to signal queue
    channel.basic_consume(on_ready_signal,
                          no_ack=False,
                          queue='bootstrapping')

    logger.info('Waiting components ready signal... signals not checked:' + str(TT_check_list))

    # wait for all testing tool component's signal
    timeout = False
    def timeout_f():
        global timeout
        timeout = True

    t = Timer(READY_SIGNAL_TOUT, timeout_f)
    t.start()

    while len(TT_check_list)!=0 and not timeout:
        time.sleep(0.3)
        connection.process_data_events()

    if timeout:
        logger.error("Some components havent sent READY signal: %s"%str(TT_check_list))
        sys.exit(1)

    logger.info('All components ready')
    assert len(TT_check_list)==0

    channel.basic_publish(
            routing_key='control.session.bootstrap',
            exchange=AMQP_EXCHANGE,
            body=json.dumps(
                    {
                        'message': 'All testing tool components are ready!',
                        "_type": 'testingtool.ready'
                    }
            ),
            properties=pika.BasicProperties(
                    content_type='application/json',
            )
    )

    # # # lets start the test suite coordination phase # # #

    try:
        logger.info('Instantiating coordinator..')
        coordinator = Coordinator(connection, TD_COAP, TD_COAP_CFG)
    except Exception as e:
        # at this level i cannot emit AMQP messages if sth fails
        error_msg = str(e)
        logger.error(' Critical exception found: %s , traceback: %s' %(error_msg,traceback.format_exc()))
        logger.debug(traceback.format_exc())
        sys.exit(1)

    ### RUN COMPONENTS ###

    try:
        logger.info('Starting coordinator execution ..')
        # start consuming messages
        coordinator.run()
        logger.info('Finishing...')

    except pika.exceptions.ConnectionClosed as cc:
        logger.error(' AMQP connection closed: %s' % str(cc))
        sys.exit(1)

    except KeyboardInterrupt as KI:
        #close AMQP connection
        connection.close()

    except Exception as e:
        error_msg = str(e)
        logger.error(' Critical exception found: %s, traceback: %s' %(error_msg,traceback.format_exc()))
        logger.debug(traceback.format_exc())

        # lets push the error message into the bus
        coordinator.channel.basic_publish(
            body = json.dumps({
                'traceback':traceback.format_exc(),
                'message': error_msg,
                '_type': 'testcoordination.error',
            }),
            exchange = AMQP_EXCHANGE,
            routing_key ='control.testcoordination.error',
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )
        #close AMQP connection
        connection.close()

        sys.exit(1)