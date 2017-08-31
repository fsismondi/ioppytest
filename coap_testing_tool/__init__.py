# -*- coding: utf-8 -*-

import os
import json


try:
    # For Python 3.0 and later
    from urllib.parse import urlparse
except ImportError:
    # Fall back to Python 2
    from urlparse import urlparse

__version__ = (0, 0, 6)

project_dir = os.path.abspath(os.path.join(os.path.realpath(__file__), os.pardir))
if os.sep + 'coap_testing_tool' in project_dir:
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


# # # # # # hard variables # # # # # # # # # #

TMPDIR = os.path.join(project_dir, 'tmp')
DATADIR = os.path.join(project_dir, 'data')
RESULTS_DIR = os.path.join(DATADIR, 'results')
PCAP_DIR = os.path.join(DATADIR, 'dumps')
LOGDIR = os.path.join(project_dir, 'log')
TD_DIR = os.path.join(project_dir, 'coap_testing_tool', 'extended_test_descriptions')
TD_COAP = os.path.join(TD_DIR, "TD_COAP_CORE.yaml")
TD_COAP_CFG = os.path.join(TD_DIR, "TD_COAP_CFG.yaml")
TD_6LOWPAN = os.path.join(TD_DIR, "TD_6LOWPAN_FORMAT.yaml")

# # # # # # ENV variables # # # # # # # # # #

# INTERACTIVE_SESSION: if not an interactive session then user input is emulated
INTERACTIVE_SESSION = get_from_environment("INTERACTIVE_SESSION", True)

# AMQP ENV variables (either get them all from ENV or set them all as default)
try:
    AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])
except KeyError as e:
    AMQP_EXCHANGE = "amq.topic"

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

# # # # # # variables coming from index.json # # # # # # # # # #

try:
    # read config information from manifest file (interoperability_manifest.json)
    with open(os.path.join(project_dir, 'coap_testing_tool', 'interoperability_manifest.json')) as index_file:
        AGENT_NAMES = json.load(index_file)['agent_names']
        print(AGENT_NAMES)

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
    AGENT_TT_ID,
    INTERACTIVE_SESSION,
    TD_6LOWPAN,
    TD_COAP,
    TD_COAP_CFG

]
