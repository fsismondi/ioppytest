import json
import logging
import click
from kombu import Connection, Exchange, Queue
from kombu.mixins import ConsumerMixin

from .tun import OpenTunLinux
DEFAULT_IPV6_PREFIX = 'bbbb'

DEFAULT_PLATFORM = "f-interop.paris.inria.fr"
LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
LOGGER = logging.getLogger("agent")

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

__version__ = (0, 0, 1)


class MyTest(ConsumerMixin):
    def __init__(self, connection, name="myTest"):
        self.name = name
        self.connection = connection
        self.producer = self.connection.Producer(serializer='json')

        self.exchange = Exchange('default', type="topic")
        self.control_queue = Queue("control_{name}".format(name=name),
                                   exchange=self.exchange,
                                   durable=True,
                                   routing_key="control.fromAgent.#")
        self.data_queue = Queue("data_{name}".format(name=name),
                                exchange=self.exchange,
                                durable=True,
                                routing_key="data.fromAgent.#")
        self.tun = OpenTunLinux(
            name=self.name,
            rmq_connection=self.connection,
            ipv6_host=":2",
            ipv6_prefix=DEFAULT_IPV6_PREFIX
        )

        log.info("Let's bootstrap this.")
        log.info("First let's start the tun device on this side")

    def get_consumers(self, Consumer, channel):
        return [
            Consumer(queues=[self.control_queue],
                     callbacks=[self.handle_control],
                     no_ack=True,
                     accept=['json']),
            Consumer(queues=[self.data_queue],
                     callbacks=[self.handle_data],
                     no_ack=True,
                     accept=["json"])
        ]

    def handle_control(self, body, message):
        """
        """
        log.info("Let's handle control messages")
        msg = None
        log.debug("Here is the type of body: %s" % type(body))
        log.debug("Here is the body")
        log.debug(body)
        log.debug("Here is the message")
        log.debug(message)

        # if type(body) == "dict":
        #     msg = body
        # else:
        #     try:
        #         msg = json.loads(body)
        #         log.debug(message)
        #     except ValueError as e:
        #         message.ack()
        #         log.error(e)
        #         log.error("Incorrect message: {0}".format(body))

        #     except TypeError as e:
        #         message.ack()
        #         log.error(e)
        #         log.error("A problem with string / buffer happened?")

        if body is not None:

            log.debug("Just received that packet")
            log.debug(body)
            if "order" in body.keys():
                if body["order"] == "bootstrap":
                    self.handle_bootstrap()

    def handle_bootstrap(self):
        log.debug("Let's start the bootstrap")
        self.producer.publish(json.dumps({"order": "tun.start",
                                          "ipv6_host": ":1",
                                          "ipv6_prefix": "bbbb"}),
                              exchange=self.exchange,
                              routing_key="control.toAgent.client")

    def handle_data(self, body, message):
        """
        """
        log.info("Let's handle data messages")
        log.debug("Here is the type of body")
        log.debug(type(body))
        log.debug("Here is the body")
        log.debug(body)
        log.debug("Here is the message")
        log.debug(message)
        msg = json.loads(body)

        # We are only with two nodes. Any packet from the client is for us.
        # These lines do the routing between the two
        if msg["routing_key"] == "data.fromAgent.client":
            log.debug("Message was routed, therefore we can inject it on our tun")
            self.tun._v6ToInternet_notif(sender="test",
                                         signal="tun",
                                         data=msg["data"])
        else:
            self.producer.publish(msg,
                                  exchange=self.exchange,
                                  routing_key="data.toAgent.client")

    def handle_routing(self):
        """
        In charge of routing packets back and forth between client and server
        Returns:

        """
        log.info("Should implement that")


@click.group()
@click.version_option(str(__version__))
def cli():
    """
    myTest package
    """
    pass


@cli.command("my_test")
@click.argument("session")
@click.option("--user",
              default="finterop",
              help="finterop AMQP username")
@click.option("--password",
              default="finterop",
              help="finterop AMQP password")
@click.option("--server",
              default=DEFAULT_PLATFORM,
              help="f-interop platform (default: %s)" % DEFAULT_PLATFORM)
def my_test(session, user, password, server):
    c = Connection(
        'amqp://{user}:{password}@{server}/{session}'.format(user=user,
                                                             password=password,
                                                             session=session,
                                                             server=server),
        transport_options={'confirm_publish': True})

    test = MyTest(c)
    test.run()


if __name__ == '__main__':
    cli()