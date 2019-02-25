# -*- coding: utf-8 -*-

import os
import json

# py2 and py3 compat
try:  # try py3 import
    from urllib.parse import urlparse
except ImportError:
    # Fall back to Python 2
    from urlparse import urlparse

__version__ = (0, 0, 6)


__all__ = [
    '__version__',
    'TMPDIR',
    'DATADIR',
    'RESULTS_DIR',
    'PCAP_DIR',
    'LOGDIR',
    'TD_DIR',
    'AMQP_URL',
    'TEST_DESCRIPTIONS_DICT',
    'TEST_DESCRIPTIONS_CONFIGS_DICT',
    'LOGGER_FORMAT'
]

project_dir = os.path.abspath(os.path.join(os.path.realpath(__file__), os.pardir))

if os.sep + 'ioppytest' in project_dir:
    project_dir = os.path.abspath(os.path.join(project_dir, os.pardir))

print('Project dir: %s' % project_dir)


def get_from_environment(variable, default):
    if variable in os.environ:
        v = os.environ.get(variable)
        print("ENVIRONMENT VAR imported: %s=%s" % (variable, default))
    else:
        v = default
        print("ENVIRONMENT VAR not found, using defaulte: %s=%s" % (variable, default))
    return v


#LOGGER_FORMAT = '%(levelname)s %(asctime)s [%(name)s] %(message)s'
LOGGER_FORMAT = '%(levelname)s [%(name)s] %(message)s'

# # # # # # hard variables # # # # # # # # # #

# python configs
LOG_LEVEL = 20  # DEBUG = 10, INFO = 20, WARNING = 30
AMQP_LOG_LEVEL = 30

# project directories
PROJECT_DIR = project_dir
TMPDIR = os.path.join(project_dir, 'tmp')
DATADIR = os.path.join(project_dir, 'data')
RESULTS_DIR = os.path.join(DATADIR, 'results')
PCAP_DIR = os.path.join(DATADIR, 'dumps')
LOGDIR = os.path.join(project_dir, 'log')
TD_DIR = os.path.join(project_dir, 'ioppytest', 'test_descriptions')

# yaml test descriptions:
# fixme: refact the code so TD_XXX is a list of yaml files containing test cases from several groups

TD_DUMMY_CFG = os.path.join(TD_DIR, "TD_DUMMY_CFG.yaml")
TD_WOT_CFG = os.path.join(TD_DIR, "TD_WOT_CFG.yaml")
TD_COAP_CORE = os.path.join(TD_DIR, "TD_COAP_CORE.yaml")
TD_COAP_CFG = os.path.join(TD_DIR, "TD_COAP_CFG.yaml")
TD_COAP = [
    TD_COAP_CORE
]

# TODO FIX REDUNDANT INFORATION IN TD AND TD CONFIGS!!!
TD_LWM2M_CFG = os.path.join(TD_DIR, "TD_LWM2M_CFG.yaml")
TD_LWM2M = [
    os.path.join(TD_DIR, "TD_LWM2M_PRO.yaml")
]

TD_COMI = [
    os.path.join(TD_DIR, "TD_COMI.yaml")
]

TD_COMI_CFG = os.path.join(TD_DIR, "TD_COMI_CFG.yaml")

TD_6LOWPAN_CFG = os.path.join(TD_DIR, "TD_6LOWPAN_CFG.yaml")

TD_6LOWPAN = [
    os.path.join(TD_DIR, "TD_6LOWPAN_HC.yaml"),
    os.path.join(TD_DIR, "TD_6LOWPAN_FORMAT.yaml"),
    os.path.join(TD_DIR, "TD_6LOWPAN_ND.yaml"),
    os.path.join(TD_DIR, "TD_6LOWPAN_RS_RA.yaml"),
]

TD_ONEM2M = [
    os.path.join(TD_DIR, "TD_ONEM2M_PRO.yaml")
]
TD_ONEM2M_CFG = os.path.join(TD_DIR, "TD_ONEM2M_PRO_CFG.yaml")


# dict values are lists of test descriptions!
TEST_DESCRIPTIONS_DICT = {
    'coap': TD_COAP,
    '6lowpan': TD_6LOWPAN,
    'onem2m': TD_ONEM2M,
    'comi': TD_COMI,
    'lwm2m': TD_LWM2M,
}

TEST_DESCRIPTIONS = [
    TD_COAP_CORE,
    TD_ONEM2M,
    TD_COMI,
    TD_6LOWPAN,
    TD_LWM2M,
]

TEST_DESCRIPTIONS_CONFIGS = [
    TD_DUMMY_CFG,
    TD_COAP_CFG,
    TD_6LOWPAN_CFG,
    TD_ONEM2M_CFG,
    TD_COMI_CFG,
    TD_LWM2M_CFG,
    TD_WOT_CFG
]

TEST_DESCRIPTIONS_CONFIGS_DICT = {
    'dummy':[TD_DUMMY_CFG],
    'coap': [TD_COAP_CFG],
    '6lowpan': [TD_6LOWPAN_CFG],
    'onem2m': [TD_ONEM2M_CFG],
    'comi': [TD_COMI_CFG],
    'lwm2m': [TD_LWM2M_CFG],
    'wot': [TD_WOT_CFG],
}

AUTO_DISSECTION_FILE = os.path.join(project_dir, '/data/auto_dissection.json')

# # # # # # ENV variables # # # # # # # # # #

# AMQP ENV variables (either get them all from ENV or set them all as default)
try:
    AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
except KeyError as e:
    AMQP_EXCHANGE = "amq.topic"

try:
    # append to URL AMQP connection parameters
    env_url = str(os.environ['AMQP_URL'])
    if 'heartbeat' not in env_url:
        AMQP_URL = '%s?%s&%s&%s&%s&%s' % (
            env_url,
            "heartbeat=0",
            "blocked_connection_timeout=2",
            "retry_delay=1",
            "socket_timeout=5",
            "connection_attempts=3"
        )
    else:
        AMQP_URL = env_url

    p = urlparse(AMQP_URL)
    AMQP_USER = p.username
    AMQP_PASS = p.password
    AMQP_SERVER = p.hostname
    AMQP_VHOST = p.path.strip('/')

except KeyError as e:

    print('Cannot retrieve environment variables for AMQP connection. Loading defaults..')
    # load default values
    AMQP_SERVER = "localhost"
    AMQP_USER = "guest"
    AMQP_PASS = "guest"
    AMQP_VHOST = "/"
    AMQP_URL = "amqp://{0}:{1}@{2}/{3}".format(AMQP_USER, AMQP_PASS, AMQP_SERVER, AMQP_VHOST)

# print(json.dumps(
#     {
#         'server': AMQP_SERVER,
#         'session': AMQP_VHOST,
#         'user': AMQP_USER,
#         'pass': '#' * len(AMQP_PASS),
#         'exchange': AMQP_EXCHANGE
#     }
# ))
