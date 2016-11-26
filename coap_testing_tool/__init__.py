# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import os
import sys

__abs_path = os.path.dirname(os.path.realpath(sys.argv[0]))
TMPDIR = os.path.join( __abs_path,'tmp')
DATADIR = os.path.join( __abs_path,'data')
LOGDIR = os.path.join( __abs_path,'log')
TD_DIR = os.path.join( __abs_path,'coap_testing_tool','extended_test_descriptions')

# lets get the AMQP params from the ENV

try:
    AMQP_SERVER = str(os.environ['AMQP_SERVER'])
    AMQP_USER = str(os.environ['AMQP_USER'])
    AMQP_PASS = str(os.environ['AMQP_PASS'])
    AMQP_VHOST = str(os.environ['AMQP_VHOST'])
    AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])


except KeyError as e:
    print('Cannot retrieve environment variables for AMQP connection. Loading defaults..')
    # default values
    AMQP_SERVER = "localhost"
    AMQP_USER = "guest"
    AMQP_PASS = "guest"
    AMQP_VHOST = "/"
    AMQP_EXCHANGE = "default"

