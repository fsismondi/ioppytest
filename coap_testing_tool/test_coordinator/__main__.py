# -*- coding: utf-8 -*-
#!/usr/bin/env python3

from coap_testing_tool.test_coordinator.coordinator import *
from coap_testing_tool import AMQP_VHOST, AMQP_PASS,AMQP_SERVER,AMQP_USER, AMQP_EXCHANGE
from coap_testing_tool import DATADIR,TMPDIR,LOGDIR,TD_DIR

COMPONENT_ID = 'test_coordinator'

# init logging to stnd output and log files
logger = initialize_logger(LOGDIR, COMPONENT_ID)

if __name__ == '__main__':


    # generate dirs
    for d in TMPDIR, DATADIR, LOGDIR:
        try:
            os.makedirs(d)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise


    ### SETUP CONNECTION ###

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

    ### INIT COMPONENTS ###
    # TODO point to the correct TED using session bootstrap message
    try:
        logger.info('Instantiating coordinator..')
        coordinator = Coordinator(connection, TD_COAP)
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