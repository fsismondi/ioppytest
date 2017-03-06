#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json

__version__ = (0, 0, 2)

project_dir = os.path.abspath(os.path.join(os.path.realpath(__file__), os.pardir))

if '/coap_testing_tool' in project_dir:
     project_dir = os.path.abspath(os.path.join(project_dir, os.pardir))

print('Project dir: %s'%project_dir)

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
    AMQP_URL = str(os.environ['AMQP_URL'])

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


try:
    # read config information from manifest file (index.json)
    with open('index.json') as o:
        AGENT_NAMES = json.load(o)['agent_names']

except:
    AGENT_NAMES = []

AGENT_TT_ID = 'agent_TT'

__all__ = [
    __version__,
    TMPDIR,
    DATADIR,
    RESULTS_DIR,
    PCAP_DIR,
    LOGDIR,
    TD_DIR,
    AMQP_SERVER,
    AMQP_URL,
    AGENT_NAMES,
    AGENT_TT_ID
]
