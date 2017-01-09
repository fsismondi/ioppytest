#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json

__version__ = (0, 0, 1)

#__abs_path = os.path.dirname(os.path.realpath(sys.argv[0]))
__abs_path = os.path.dirname(os.path.realpath(__file__))
project_dir = os.path.join(__abs_path, '..')

TMPDIR = os.path.join( project_dir,'tmp')
DATADIR = os.path.join( project_dir,'data')
RESULTS_DIR = os.path.join( DATADIR,'results')
PCAP_DIR =  os.path.join( DATADIR,'dumps')
LOGDIR = os.path.join( project_dir,'log')
TD_DIR = os.path.join( project_dir,'coap_testing_tool','extended_test_descriptions')

# lets get the AMQP params from the ENV


# rewrite default values with ENV variables
try:
    AMQP_SERVER = str(os.environ['AMQP_SERVER'])
    AMQP_USER = str(os.environ['AMQP_USER'])
    AMQP_PASS = str(os.environ['AMQP_PASS'])
    AMQP_VHOST = str(os.environ['AMQP_VHOST'])
    AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
    print('Env vars for AMQP connection succesfully imported')

except KeyError as e:
    print('Cannot retrieve environment variables for AMQP connection. Loading defaults..')
    # default values
    AMQP_SERVER = "localhost"
    AMQP_USER = "guest"
    AMQP_PASS = "guest"
    AMQP_VHOST = "/"
    AMQP_EXCHANGE = "default"

print(json.dumps(
            {
                'server': AMQP_SERVER,
                'session': AMQP_VHOST,
                'user': AMQP_USER,
                'pass': '#' * len(AMQP_PASS),
                'exchange': AMQP_EXCHANGE
            }
    ))