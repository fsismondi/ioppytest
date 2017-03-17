#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
from urllib.parse import urlparse

__version__ = (0, 0, 4)

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
TD_COAP = os.path.join(TD_DIR,"TD_COAP_CORE.yaml")
TD_COAP_CFG = os.path.join(TD_DIR,"TD_COAP_CFG.yaml")

# lets get the AMQP params from the ENV


try:
    AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
except KeyError as e:
    AMQP_EXCHANGE = "default"

try:
    AMQP_URL = str(os.environ['AMQP_URL'])
    p = urlparse(AMQP_URL)
    AMQP_USER = p.username
    AMQP_PASS = p.password
    AMQP_SERVER = p.hostname
    AMQP_VHOST = p.path.strip('/')

    print('Env vars for AMQP connection succesfully imported')

except KeyError as e:

    print('Cannot retrieve environment variables for AMQP connection. Loading defaults..')
    # load default values
    AMQP_SERVER = "localhost"
    AMQP_USER = "guest"
    AMQP_PASS = "guest"
    AMQP_VHOST = "/"
    AMQP_URL = "amqp://{0}:{1}@{2}/{3}".format(AMQP_USER, AMQP_PASS, AMQP_SERVER, AMQP_VHOST)

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
    with open('index.json') as index_file:
        AGENT_NAMES = json.load(index_file)['agent_names']

except:
    print('Cannot retrieve agent config from index file of the testing tool')
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
    AMQP_URL,
    AGENT_NAMES,
    AGENT_TT_ID
]
