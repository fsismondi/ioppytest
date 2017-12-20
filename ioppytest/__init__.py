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

project_dir = os.path.abspath(os.path.join(os.path.realpath(__file__), os.pardir))

if os.sep + 'ioppytest' in project_dir:
    project_dir = os.path.abspath(os.path.join(project_dir, os.pardir))

print('Project dir: %s' % project_dir)


def get_from_environment(variable, default):
    if variable in os.environ:
        v = os.environ.get(variable)
        print("Using environment variable %s=%s" % (variable, default))
    else:
        v = default
        print("Using default variable %s=%s" % (variable, default))
    return v

LOGGER_FORMAT = '%(levelname)s %(name)s [%(threadName)s] %(message)s'

# # # # # # hard variables # # # # # # # # # #

# python configs
LOG_LEVEL = 20  # logging.INFO -> 20, logging.WARNING -> 30
AMQP_LOG_LEVEL = 30

# project directories
PROJECT_DIR = project_dir
TMPDIR = os.path.join(project_dir, 'tmp')
DATADIR = os.path.join(project_dir, 'data')
RESULTS_DIR = os.path.join(DATADIR, 'results')
PCAP_DIR = os.path.join(DATADIR, 'dumps')
LOGDIR = os.path.join(project_dir, 'log')
TD_DIR = os.path.join(project_dir, 'ioppytest', 'extended_test_descriptions')

# yaml test descriptions:
TD_COAP = os.path.join(TD_DIR, "TD_COAP_CORE.yaml")
TD_COAP_CFG = os.path.join(TD_DIR, "TD_COAP_CFG.yaml")

TD_COMI = os.path.join(TD_DIR, "TD_COMI.yaml")
TD_COMI_CFG = os.path.join(TD_DIR, "TD_COMI_CFG.yaml")

TD_6LOWPAN = os.path.join(TD_DIR, "TD_6LOWPAN_FORMAT.yaml")
TD_6LOWPAN_CFG = os.path.join(TD_DIR, "TD_6LOWPAN_CFG.yaml")

TD_ONEM2M = os.path.join(TD_DIR, "TD_ONEM2M_PRO.yaml")
TD_ONEM2M_CFG = os.path.join(TD_DIR, "TD_ONEM2M_PRO_CFG.yaml")

TEST_DESCRIPTIONS = [TD_COAP, TD_6LOWPAN, TD_ONEM2M, TD_COMI]
TEST_DESCRIPTIONS_CONFIGS = [TD_COAP_CFG, TD_6LOWPAN_CFG, TD_ONEM2M_CFG, TD_COMI_CFG]

AUTO_DISSECTION_FILE = os.path.join(project_dir, 'ioppytest/test_analysis_tool/data/auto_dissection.json')

# # # # # # ENV variables # # # # # # # # # #

# INTERACTIVE_SESSION: if not an interactive session then user input is emulated
INTERACTIVE_SESSION = get_from_environment("INTERACTIVE_SESSION", True)

# AMQP ENV variables (either get them all from ENV or set them all as default)
try:
    AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
except KeyError as e:
    AMQP_EXCHANGE = "amq.topic"

try:

    # append to URL AMQP connection parameters
    env_url = str(os.environ['AMQP_URL'])
    if 'heartbeat_interval' not in env_url:
        AMQP_URL = '%s?%s&%s&%s&%s&%s' % (
            env_url,
            "heartbeat_interval=0",
            "blocked_connection_timeout=300",
            "retry_delay=1",
            "socket_timeout=1",
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

print(json.dumps(
    {
        'server': AMQP_SERVER,
        'session': AMQP_VHOST,
        'user': AMQP_USER,
        'pass': '#' * len(AMQP_PASS),
        'exchange': AMQP_EXCHANGE
    }
))

# # # # # # variables coming from index.json # # # # # # # # # #


__all__ = [
    __version__,
    TMPDIR,
    DATADIR,
    RESULTS_DIR,
    PCAP_DIR,
    LOGDIR,
    TD_DIR,
    AMQP_URL,
    INTERACTIVE_SESSION,
    TD_6LOWPAN,
    TD_6LOWPAN_CFG,
    TD_ONEM2M,
    TD_ONEM2M_CFG,
    TD_COMI,
    TD_COMI_CFG,
    TD_COAP,
    TD_COAP_CFG,
    LOGGER_FORMAT
]
