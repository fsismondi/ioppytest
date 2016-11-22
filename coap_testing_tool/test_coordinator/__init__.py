from requests.auth import HTTPBasicAuth

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
version = (0, 0, 1)
RABBITMQ_API = "http://localhost:15672/api"
RABBITMQ_CREDENTIALS = HTTPBasicAuth('finterop', 'finterop')
DEFAULT_PLATFORM = "f-interop.paris.inria.fr"
DEFAULT_EXCHANGE = "default"
DEFAULT_IPV6_PREFIX = "bbbb"
