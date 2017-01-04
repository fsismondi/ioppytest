import json
import logging
import click
from kombu import Connection, Exchange, Queue
from kombu.mixins import ConsumerMixin
import uuid

from tun import OpenTunLinux, OpenTunMACOS
DEFAULT_IPV6_PREFIX = 'bbbb'

DEFAULT_PLATFORM = "f-interop.paris.inria.fr"
LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
LOGGER = logging.getLogger("agent")

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

__version__ = (0, 0, 1)


class Agent(ConsumerMixin):
    """
    Command line interface of the agent
    """

    header = """
    F-interop agent and management tool.

    For more information, visit: http://f-interop.paris.inria.fr.
    """,

    def __init__(self):

        self.cli = click.Group(
                add_help_option=Agent.header,
                short_help=Agent.header
        )

        # Options

        self.user_option = click.Option(
                param_decls=["--user"],
                required=True,
                help="F-interop username."
        )

        self.password_option = click.Option(
                param_decls=["--password"],
                required=True,
                help="F-interop password.",
                hide_input=True)

        self.session_option = click.Option(
                param_decls=["--session"],
                required=True,
                help="F-interop session id."
        )

        self.server_option = click.Option(
                param_decls=["--server"],
                default=DEFAULT_PLATFORM,
                required=True,
                help="f-interop platform (default: %s)" % DEFAULT_PLATFORM)

        self.name_option = click.Option(
                param_decls=["--name"],
                default="agent_automated_iut",
                required=True,
                help="Agent identity (default: random generated)")

        # Commands

        self.connect_command = click.Command(
                "connect",
                callback=self.handle_connect,
                params=[self.user_option,
                        self.password_option,
                        self.session_option,
                        self.server_option,
                        self.name_option],
                short_help="Authenticate user")

        self.cli.add_command(self.connect_command)

        self.name = self.name_option


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

    def handle_connect(self, user, password, session, server, name):
        """
        Authenticate a USER with an f-interop.

        This create a file/token that is reused to access the f-interop platform.
        """
        data = {
            "user": user,
            "password": password,
            "session": session,
            "server": server,
            "name": name
        }
        log.info("Try to connect with %s" % data)

        self.connection = Connection(
                'amqp://{user}:{password}@{server}/{session}'.format(user=user,
                                                                     password=password,
                                                                     session=session,
                                                                     server=server),
                transport_options={'confirm_publish': True})

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

        self.tun = OpenTunMACOS(
            name=self.name,
            rmq_connection=self.connection,
            ipv6_host=":2",
            ipv6_prefix=DEFAULT_IPV6_PREFIX
        )

        # self.tun = OpenTunLinux(
        #     name=self.name,
        #     rmq_connection=self.connection,
        #     ipv6_host=":2",
        #     ipv6_prefix=DEFAULT_IPV6_PREFIX
        # )

        log.info("Let's bootstrap this.")

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

    def run(self):
        self.cli()


if __name__ == '__main__':
    agent = Agent()
    agent.run()
