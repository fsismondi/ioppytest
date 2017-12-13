import os
import pika
import logging
import argparse
import threading
import traceback
from ioppytest.utils.messages import *
from ioppytest.utils.event_bus_utils import AmqpListener
from ioppytest.utils.tabulate import tabulate


logging.getLogger('pika').setLevel(logging.WARNING)

logging.basicConfig(level=logging.DEBUG,
                    format='[%(levelname)s] (%(threadName)-10s): %(message)s', )

TESTING_TOOL_TOPIC_SUBSCRIPTIONS = [
    MsgTestSuiteStart.routing_key,
    MsgTestingToolTerminate.routing_key,
    '#.fromAgent.#',
]

AMQP_URL = os.environ.get('AMQP_URL')
AMQP_EXCHANGE = os.environ.get('AMQP_EXCHANGE')

STDOUT_MAX_STRING_LENGTH = 70

MESSAGES_NOT_TO_BE_ECHOED = [
    MsgTestCaseStarted
]

UI_REPLY_TOPICS = [
    'ui.user.1.reply',
    'ui.user.2.reply',
    'ui.user.all.reply',
]

env_vars_export = """
Export environment variables: 

`export AMQP_URL=%s`

`export AMQP_EXCHANGE=%s`
""" % (AMQP_URL, AMQP_EXCHANGE)

agents_IP_tunnel_config = """

### Please download the agent component (python script):

`git clone --recursive https://gitlab.f-interop.eu/f-interop-contributors/agent`

------------------------------------------------------------------------------

### Install dependencies:

`pip install -r requirements.txt`

------------------------------------------------------------------------------
### Run (choose if either SomeAgentName1 or SomeAgentName2):

`sudo -E python agent.py connect --url $AMQP_URL --exchange $AMQP_EXCHANGE  --name SomeAgentName1`

or

`sudo -E python agent.py connect --url $AMQP_URL --exchange $AMQP_EXCHANGE  --name SomeAgentName2`

------------------------------------------------------------------------------

### What is this for?

The agent creates a tun interface in your PC which allows you to comminicate with other implementations, the 
solution goes more or less like this:
```
                          +----------------+
                          |                |
                          |   AMQP broker  |
                          |                |
                          +----------------+
                                ^     +
                                |     |
data.tun.fromAgent.agent_name   |     |  data.tun.toAgent.agent_name
                                |     |
                                +     v
                 +---------------------------------+
                 |                                 |
                 |             Agent               |
                 |           (tun mode)            |
                 |                                 |
                 |   +------tun interface--------+ |
                 |  +----------------------------+ |
                 |  |         IPv6-based         | |
                 |  |        communicating       | |
                 |  |      piece of software     | |
                 |  |      (e.g. coap client)    | |
                 |  +----------------------------+ |
                 +---------------------------------+
```

------------------------------------------------------------------------------

### How do I know it's working?

If everything goes well you should see in your terminal sth like this:

fsismondi@carbonero250:~/dev/agent$ sudo -E python agent.py connect --url $AMQP_URL --exchange $AMQP_EXCHANGE --name coap_client
Password:

      ______    _____       _                       
     |  ____|  |_   _|     | |                      
     | |__ ______| |  _ __ | |_ ___ _ __ ___  _ __  
     |  __|______| | | '_ \| __/ _ \ '__/ _ \| '_ \ 
     | |        _| |_| | | | ||  __/ | | (_) | |_) |
     |_|       |_____|_| |_|\__\___|_|  \___/| .__/ 
                                             | |    
                                             |_|    

INFO:__main__:Try to connect with {'session': u'session05', 'user': u'paul', (...)
INFO:kombu.mixins:Connected to amqp://paul:**@f-interop.rennes.inria.fr:5672/session05
INFO:connectors.tun:tun listening to control plane 
INFO:connectors.tun:Queue: control.tun@coap_client 
INFO:connectors.tun:Topic: control.tun.toAgent.coap_client
INFO:connectors.tun:tun listening to data plane
INFO:connectors.tun:Queue: data.tun@coap_client
INFO:connectors.tun:Topic: data.tun.toAgent.coap_client
INFO:kombu.mixins:Connected to amqp://paul:**@f-interop.rennes.inria.fr:5672/session05
INFO:connectors.core:Backend ready to consume data

------------------------------------------------------------------------------

### Test1 : check the tun interface was created (unless agent was runned in --serial mode) 
\n\n
Then after the user triggers **test suite start** should see a new network interface in your PC:
\n\n
`fsismondi@carbonero250:~$ ifconfig`
\n\n
should show:
\n\n
```
    tun0: flags=8851<UP,POINTOPOINT,RUNNING,SIMPLEX,MULTICAST> mtu 1500
        inet6 fe80::aebc:32ff:fecd:f38b%tun0 prefixlen 64 scopeid 0xc 
        inet6 bbbb::1 prefixlen 64 
        inet6 fe80::1%tun0 prefixlen 64 scopeid 0xc 
        nd6 options=201<PERFORMNUD,DAD>
        open (pid 7627)
```

----------------------------------------------------------------------------

### Test2 : ping the other device (unless agent was runned in --serial mode) 
\n\n
Now you could try ping6 the other implementation in the VPN:
\n\n
`fsismondi@carbonero250:~$ ping6 bbbb::2`
\n\n
should show:
\n\n
```
    fsismondi@carbonero250:~$ ping6 bbbb::2
    PING6(56=40+8+8 bytes) bbbb::1 --> bbbb::2
    16 bytes from bbbb::2, icmp_seq=0 hlim=64 time=65.824 ms
    16 bytes from bbbb::2, icmp_seq=1 hlim=64 time=69.990 ms
    16 bytes from bbbb::2, icmp_seq=2 hlim=64 time=63.770 ms
    ^C
    --- bbbb::2 ping6 statistics ---
    3 packets transmitted, 3 packets received, 0.0% packet loss
    round-trip min/avg/max/std-dev = 63.770/66.528/69.990/2.588 ms
```

----------------------------------------------------------------------------

### More about the agent component:

[link to agent README](https://gitlab.f-interop.eu/f-interop-contributors/agent/blob/master/README.md)

\n\n
"""


# TODO import this from event bus utils once we have sth stable regarding threaded uses of connections
def publish_message(connection, message):
    """
    Publishes message into the correct topic (uses Message object metadata)
    Creates temporary channel on it's own
    Connection must be a pika.BlockingConnection
    """
    channel = None

    logging.debug('[PUBLISHING] %s' % repr(connection))
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))  # this doesnt overwrite connection argument!
    try:
        channel = connection.channel()

        properties = pika.BasicProperties(**message.get_properties())

        channel.basic_publish(
            exchange=AMQP_EXCHANGE,
            routing_key=message.routing_key,
            properties=properties,
            body=message.to_json(),
        )

    finally:
        if channel and channel.is_open:
            channel.close()


def translate_ioppytest_description_format_to_tabulate(ls):
    """
        we get stuff like:

        as output we need:

    """
    # fixme change ioppytest format to meet tabulates requirements, their fromat for describing tables makes more sense!
    ret = []
    for item in ls:
        if type(item) is str:
            ret.append([item])
        elif type(item) is list:
            for subitem in item:
                ret.append([' ', subitem])
        else:
            logging.warning("Got unexpected table format %s" % type(item))

    logging.debug("converted table: %s" % ret)

    return ret


def list_to_str(ls):
    """
    flattens a nested list up to two levels of depth

    :param ls: the list, supports str also
    :return: single string with all the items inside the list
    """

    ret = ''

    if ls is None:
        return 'None'

    if type(ls) is str:
        return ls

    try:
        for l in ls:
            if l and isinstance(l, list):
                for sub_l in l:
                    if sub_l and not isinstance(sub_l, list):
                        ret += str(sub_l) + ' \n '
                    else:
                        # I truncate in the second level
                        pass
            else:
                ret += str(l) + ' \n '

    except TypeError as e:
        logging.error(e)
        return str(ls)

    return ret


class MessageFactory(object):
    """
    This class acts as a transformation filter between TT messages and UI messages, and as a UI messages
    creator for certain generic session user actions.

    Request format:
        MsgUiRequestConfirmationButton(fields = [
            {
                'value': True,
                'type': 'button',
                'name': 'start_test_suite'
            }
            (...)
        ]

        Reply format:
        Message(fields = [
            {
                'start_test_suite': True
            },
            (..)
        ]

    """

    def __init__(self):

        self._current_tc = None
        self._current_step = None
        self._report = None
        self._pending_responses = {}
        self.specialized_visualization = {

            # test suite messages
            MsgTestingToolReady: self._echo_message_highlighted_description,
            MsgTestCaseFinished: self._echo_message_highlighted_description,
            MsgStepStimuliExecute: self._echo_message_steps,
            MsgStepStimuliExecuted: self._echo_message_highlighted_description,
            MsgStepVerifyExecute: self._echo_message_steps,
            MsgStepVerifyExecuted: self._echo_message_highlighted_description,
            MsgConfigurationExecute: self._echo_testcase_configure,
            MsgTestSuiteReport: self._echo_test_suite_results,

            # verdicts
            MsgTestCaseVerdict: self._echo_testcase_verdict,

            # important messages
            MsgTestingToolTerminate: self._echo_message_highlighted_description,
            MsgTestingToolConfigured: self._echo_message_highlighted_description,

            # agents data messages
            MsgPacketInjectRaw: self._echo_packet_raw,
            MsgPacketSniffedRaw: self._echo_packet_raw,

            # tagged as debugging
            MsgSessionConfiguration: self._echo_as_debug_messages,
            MsgSessionLog: self._echo_as_debug_messages,
            MsgTestingToolComponentReady: self._echo_as_debug_messages,
            MsgAgentConfigured: self._echo_as_debug_messages,
            MsgAgentTunStart: self._echo_as_debug_messages,
            MsgAgentTunStarted: self._echo_as_debug_messages,
            MsgTestCaseReady: self._echo_as_debug_messages,

            # barely important enough to not be in the debugging
            MsgTestingToolComponentShutdown: self._echo_message_description_and_component,
            MsgTestCaseStarted: self._echo_message_highlighted_description,
            MsgTestCaseStart: self._echo_message_highlighted_description,
            MsgTestSuiteStarted: self._echo_message_highlighted_description,
            MsgTestSuiteStart: self._echo_message_highlighted_description,
            MsgConfigurationExecuted: self._echo_message_highlighted_description,
        }

        self.tt_to_ui_message_translation = {
            MsgTestingToolConfigured: self._ui_request_testsuite_start,
            MsgTestCaseReady: self._ui_request_testcase_start,
            MsgStepStimuliExecute: self._ui_request_step_stimuli_executed,
            MsgStepVerifyExecute: self._ui_request_step_verification,
        }

        self.ui_to_tt_message_translation = {
            'ts_start': self._tt_message_testsuite_start,
            'ts_abort': self._tt_message_testsuite_abort,
            'tc_start': self._tt_message_testcase_start,
            'tc_restart': self._tt_message_testcase_restart,
            'tc_skip': self._tt_message_testcase_skip,
            # 'tc_list': self._handle_get_testcase_list,
            # 'tc_select': self._handle_testcase_select,
            'verify_executed': self._tt_message_step_verify_executed,
            'stimuli_executed': self._tt_message_step_stimuli_executed,
        }

    def update_state(self, message):
        """
            Updates message factory states, every received message needs to be passed to this method
        """
        try:
            self._current_tc = message.testcase_id
        except AttributeError:
            pass

        try:
            self._current_step = message.step_id
        except AttributeError:
            pass

        # print states table
        status_table = [['current testcase id', 'current test step id']]
        status_table.append([self._current_tc, self._current_step])
        print(tabulate(status_table, tablefmt="grid", headers="firstrow"))

    def tag_message(self, msg):
        """
            Updates message tags of message before being sent to UI. Every message to UI needs to be passed to this
            method before being piublished
        """
        if msg and not msg.tags:

            if self._current_tc:
                msg.tags = {"testcase": self._current_tc}

            else:
                msg.tags = {"config:": 'misc.'}

        return msg

    def get_ui_request_action_message(self, message_from_tt: Message):
        """
        translates:  (message_from_tt) -> a UI request
        :returns Message for UI or None
        """

        try:
            action = self.tt_to_ui_message_translation[type(message_from_tt)]
            ui_request_message = action(message_from_tt)
            return ui_request_message

        except KeyError:
            logging.debug("Action %s not found in tt_to_ui translation table" % repr(message_from_tt))
            return None

    def translate_ui_to_tt_message(self, reply_received_from_ui):
        """
        translates:  (ui response , pending messages table) -> a TT response
        :returns Message for TT or None

        """

        # get table entry inserted on UI request

        table_entry = self.pop_pending_response(reply_received_from_ui.correlation_id)
        ui_request_message = table_entry['request_message']
        ui_requested_fields = table_entry['requested_field_list']

        response_fields_names = MessageFactory.get_field_keys_from_ui_reply(reply_received_from_ui)
        if len(response_fields_names) > 1:  # fixme
            raise Exception("UI returned a reply with two or more fields : %s " % reply_received_from_ui.fields)

        user_input_action = response_fields_names[0]  # fixme

        assert user_input_action in ui_requested_fields

        # get the value of the field from reply_received_from_ui
        user_input_value = self.get_field_value_from_ui_reply(reply_received_from_ui, user_input_action)

        try:
            message_for_tt = self.ui_to_tt_message_translation[user_input_action](user_input_value)
        except KeyError:
            logging.debug("No chained action to reply %s" % repr(reply_received_from_ui)[:STDOUT_MAX_STRING_LENGTH])
            return None

        logging.debug("UI reply :%s translated into TT message %s"
                      % (
                          repr(reply_received_from_ui),
                          repr(message_for_tt)
                      ))
        return message_for_tt

    def transform_message_to_ui_markdown_display(self, message: Message):
        msg_ret = None

        # search for specialized visualization, returns fields
        if type(message) in self.specialized_visualization:
            specialized_visualization = self.specialized_visualization[type(message)]
            msg_ret = specialized_visualization(message)

        # generic message visualization (message as a table)
        else:

            msg_ret = self._echo_message_as_table(message)

        msg_ret = self.tag_message(msg_ret)
        return msg_ret

    def transform_string_to_ui_markdown_display(self, text=None):

        msg = MsgUiDisplayMarkdownText()

        fields = [
            {
                'type': 'p',
                'value': text
            }
        ]

        msg.fields = fields

        return msg

    def add_pending_response(self, corr_id, requested_field_name_list: list, request_message):
        """
        Adds pending response to table. Note that this overwrites entries with same corr_id
        :param corr_id: Correlation id of request/reply
        :param requested_field_name_list: The list of fields names in the UI request
        :param request_message: Message originating the request in the first place
        :return:
        """
        self._pending_responses[corr_id] = {
            'request_message': request_message,
            'requested_field_list': requested_field_name_list,
        }

        logging.debug(
            "Updated pending response table,adding corr id %s | entry %s"
            % (
                corr_id,
                self._pending_responses[corr_id]
            )
        )

        self.print_table_of_pending_messages()

    def print_table_of_pending_messages(self):
        table = [['Correlation Id', 'Message sent to UI', 'Field name request (list)']]
        for key, value in self._pending_responses.items():
            entry = [
                key,
                repr(value['request_message'])[:STDOUT_MAX_STRING_LENGTH],
                value['requested_field_list'][:STDOUT_MAX_STRING_LENGTH]
            ]
            table.append(entry)

        print(tabulate(table, tablefmt="grid", headers="firstrow"))

    def get_pending_messages_correlation_id(self):
        return list(self._pending_responses.keys())

    def pop_pending_response(self, correlation_id):
        ret = None

        if correlation_id in self._pending_responses:
            ret = self._pending_responses.pop(correlation_id, None)

        logging.debug("Updated pending response table")
        self.print_table_of_pending_messages()
        return ret

    def is_pending_response(self, message):
        try:
            return message.correlation_id in self._pending_responses
        except AttributeError:
            return False

    @classmethod
    def get_field_keys_from_ui_request(cls, ui_message):
        """
        :return: list with all field names in request
        """

        fields_requested = [i['name'] for i in ui_message.fields if 'name' in i.keys()]
        return fields_requested

    @classmethod
    def get_field_keys_from_ui_reply(cls, ui_message):
        """
        :return: list with all field names in reply
        """

        l = set()
        for item in ui_message.fields:
            l |= set(item.keys())
        return list(l)

    @classmethod
    def get_field_value_from_ui_reply(cls, ui_message, field):
        for f in ui_message.fields:
            try:
                return f[field]
            except KeyError:
                pass

        return None

    # # # # # # #  TT -> UI translation to be implemented BY CHILD CLASS # # # # # # #

    def _ui_request_testsuite_start(self, message_from_tt):
        raise NotImplementedError()

    def _ui_request_testcase_start(self, message_from_tt):
        raise NotImplementedError()

    def _ui_request_step_verification(self, message_from_tt):
        raise NotImplementedError()

    def _ui_request_step_stimuli_executed(self, message_from_tt):
        raise NotImplementedError()

    # # # # # # #  UI -> TT translation to be implemented BY CHILD CLASS # # # # # # #

    def _tt_message_testsuite_start(self, user_input):
        raise NotImplementedError()

    def _tt_message_testsuite_abort(self, user_input):
        raise NotImplementedError()

    def _tt_message_testcase_start(self, user_input):
        raise NotImplementedError()

    def _tt_message_testcase_restart(self, user_input):
        raise NotImplementedError()

    def _tt_message_testcase_skip(self, user_input):
        raise NotImplementedError()

    def _tt_message_step_verify_executed(self, user_input):
        raise NotImplementedError()

    def _tt_message_step_stimuli_executed(self, user_input):
        raise NotImplementedError()

    # # # # # # # # # # # GENERIC MESSAGE UI VISUALISATION # # # # # # # # # # # # # # #

    def _echo_message_as_table(self, message):

        msg_ret = MsgUiDisplayMarkdownText()

        # convert message to table
        d = message.to_dict()
        table = []
        for key, value in d.items():
            if type(value) is list:
                temp = [key, list_to_str(value)]
            else:
                temp = [key, str(value)]
            table.append(temp)

        # prepare fields
        markdown_string = tabulate(table, tablefmt="grid").replace('\n', ' \n\n ')
        msg_ret.fields = [{
            'type': 'p',
            'value': markdown_string
        }]

        return msg_ret

    # # # # # # # # # # # PERSONALIZED MESSAGES VISUALISATION # # # # # # # # # # # # # # #

    def _echo_testcase_verdict(self, message):
        verdict = message.to_dict()
        # fixme find a way of managing the "printable" fields, in a generic way
        verdict.pop('_type')
        verdict.pop('_api_version')

        partial_verdict = verdict.pop('partial_verdicts')
        ui_fields = []
        table_result = []

        for key, value in verdict.items():
            if type(value) is list:
                temp = [key, list_to_str(value)]
            else:
                temp = [key, value]
            table_result.append(temp)

        ui_fields.append(
            {
                'type': 'p',
                'value': tabulate(table_result)
            }
        )

        if partial_verdict:
            table_partial_verdicts = []
            frames = []
            table_partial_verdicts.append(('Step ID', 'Partial verdict', 'Description'))
            for item in partial_verdict:
                try:
                    assert type(item) is list
                    cell_1 = item.pop(0)
                    cell_2 = item.pop(0)
                    cell_3 = list_to_str(item)
                    if 'Frame' in list_to_str(item):
                        frames.append(item)
                    table_partial_verdicts.append((cell_1, cell_2, cell_3))
                except Exception as e:
                    logging.error(e)
                    logging.error(traceback.format_exc())
                    break

            ui_fields.append(
                {
                    'type': 'p',
                    'value': "Frames:\n%s" % tabulate(frames)
                }
            )

            ui_fields.append(
                {
                    'type': 'p',
                    'value': tabulate(table_partial_verdicts, headers="firstrow")
                }
            )

        return MsgUiDisplayMarkdownText(
            title="Verdict on TEST CASE: %s" % self._current_tc,
            level='highlighted',
            fields=ui_fields
        )

    def _echo_test_suite_results(self, message):
        ret = self._echo_message_as_table(message)
        ret.tags = {'results': ' '}

    def _echo_message_description_and_component(self, message):
        fields = [
            {
                'type': 'p',
                'value': '%s: %s' % (message.component, message.description)
            }
        ]
        return MsgUiDisplayMarkdownText(fields=fields)

    def _echo_message_highlighted_description(self, message):
        fields = [
            {
                'type': 'p',
                'value': message.description
            }
        ]

        return MsgUiDisplayMarkdownText(level='highlighted', tags={"config:": 'misc.'}, fields=fields)

    def _echo_message_steps(self, message):
        """
        STIMULI:

         description            Please execute step: TD_COAP_CORE_01_step_01
                                 Step description: ['Client is requested to send a GET request with', ['Type = 0(CON)', 'Code = 1(GET)']]
         target_address         coap://[bbbb::2]:5683
         _api_version           0.1.48
         node                   coap_client
         testcase_ref           http://doc.f-interop.eu/tests/TD_COAP_CORE_01
         state                  executing
         step_id                TD_COAP_CORE_01_step_01
         node_execution_mode    user_assisted
         testcase_id            TD_COAP_CORE_01
         step_type              stimuli
         node_address
         step_state             executing
         _type                  testcoordination.step.stimuli.execute
         step_info              Client is requested to send a GET request with
                                 Type = 0(CON)
                                 Code = 1(GET)

        or
        VERIFY:

         step_info              Client displays the received information
         description            Please execute step: TD_COAP_CORE_01_step_04
                                 Step description: ['Client displays the received information']
         _api_version           0.1.71
         testcase_id            TD_COAP_CORE_01
         step_id                TD_COAP_CORE_01_step_04
         node_execution_mode    user_assisted
         node_address
         node                   coap_client
         testcase_ref           http://doc.f-interop.eu/tests/TD_COAP_CORE_01
         _type                  testcoordination.step.verify.execute
         step_type              verify
         step_state             executing
         state                  executing
         response_type          bool

        """
        fields_to_translate = ['step_id', 'node', 'target_address', 'testcase_ref']
        fields = []
        for f in fields_to_translate:
            try:
                fields.append({
                    'type': 'p',
                    'value': '%s: %s' % (f, getattr(message, f))
                })
            except AttributeError as ae:
                logging.error(ae)

        fields.append({
            'type': 'p',
            'value': '%s' %
                     tabulate(translate_ioppytest_description_format_to_tabulate(message.step_info), tablefmt="grid", )
        })

        return MsgUiDisplayMarkdownText(
            title="Please execute/verify the STEP: %s" % message.step_id,
            level='info',
            fields=fields
        )

    def _echo_testcase_configure(self, message):

        """
        +------------------+-----------------------------------------------+
        | state            | configuring                                   |
        +------------------+-----------------------------------------------+
        | _type            | testcoordination.configuration.execute        |
        +------------------+-----------------------------------------------+
        | _api_version     | 0.1.71                                        |
        +------------------+-----------------------------------------------+
        | testcase_id      | TD_COAP_CORE_01                               |
        +------------------+-----------------------------------------------+
        | configuration_id | COAP_CFG_01                                   |
        +------------------+-----------------------------------------------+
        | testcase_ref     | http://doc.f-interop.eu/tests/TD_COAP_CORE_01 |
        +------------------+-----------------------------------------------+
        | description      | No special configuration needed               |
        |                  |  CoAP client requests                         |
        |                  |  Destination IP Address = [bbbb::2]           |
        |                  |  Destination UDP Port = 5683                  |
        +------------------+-----------------------------------------------+
        | node             | coap_client                                   |
        +------------------+-----------------------------------------------+
        """

        fields_to_translate = ['testcase_id', 'testcase_ref', 'node', 'state']
        fields = []
        for f in fields_to_translate:
            try:
                fields.append({
                    'type': 'p',
                    'value': '%s: %s' % (f, getattr(message, f))
                })
            except AttributeError as ae:
                logging.error(ae)

        fields.append({
            'type': 'p',
            'value': '%s' %
                     (
                         tabulate(translate_ioppytest_description_format_to_tabulate(message.description),
                                  tablefmt="grid", )
                     )
        })

        return MsgUiDisplayMarkdownText(
            title="Please configure the IUT as indicated",
            level='info',
            fields=fields
        )

    def _echo_packet_raw(self, message):
        fields = []

        dir = []
        if 'fromAgent' in message.routing_key:
            dir = 'AGENT -> TESTING TOOL'
        elif 'toAgent' in message.routing_key:
            dir = 'TESTING TOOL -> AGENT'

        fields.append({
            'type': 'p',
            'value': '%s: %s' % ('data packet', dir)
        })

        fields.append({
            'type': 'p',
            'value': '%s:%s' % ('timestamp', message.timestamp)
        })
        fields.append({
            'type': 'p',
            'value': '%s:%s' % ('interface', message.interface_name)
        })

        network_bytes_aligned = ''
        count = 0
        for int_value in message.data:
            network_bytes_aligned += format(int_value, '02x')
            if count == 7:
                network_bytes_aligned += ' \t'
                count += 1
            if count == 15:
                network_bytes_aligned += ' \n'
                count = 0
            else:
                network_bytes_aligned += ' '
                count += 1

        fields.append({
            'type': 'p',
            'value': '\n%s' % (network_bytes_aligned)
        })

        return MsgUiDisplayMarkdownText(level='info', fields=fields)

    def _echo_session_configuration(self, message):
        fields = []

        fields.append({
            'type': 'p',
            'value': '%s: %s' % ('session_id', message.session_id)
        })

        fields.append({
            'type': 'p',
            'value': '%s:%s' % ('users', message.users)
        })
        fields.append({
            'type': 'p',
            'value': '%s:%s' % ('testing_tools', message.testing_tools)
        })

        try:
            testcases = message.configuration['testsuite.testcases']
            fields.append({
                'type': 'p',
                'value': '%s:%s' % ('testcases', testcases)
            })
        except Exception as e:
            logging.warning('No testsuite.testcases in %s ' % repr(message))

        try:
            additional_session_resource = message.configuration['testsuite.additional_session_resource']
            fields.append({
                'type': 'p',
                'value': '%s:%s' % ('additional_session_resource', additional_session_resource)
            })
        except Exception as e:
            logging.warning("No testsuite.additional_session_resource in %s " % repr(message))

        return MsgUiDisplayMarkdownText(
            title='This is the session configuration',
            level='info',
            fields=fields)

    def _echo_as_debug_messages(self, message):

        ret_msg = self._echo_message_as_table(message)
        ret_msg.tags = {"logs": " "}
        return ret_msg


class CoAPSessionMessageFactory(MessageFactory):
    AGENT_NAMES = ['coap_client', 'coap_server']

    def __init__(self):
        super().__init__()

    @classmethod
    def get_amqp_url_connection_message(cls):
        message_ui_request = MsgUiRequestConfirmationButton()
        message_ui_request.fields = [
            {
                "type": "p",
                "value": env_vars_export
            },
            {
                "name": "Done",
                "type": "button",
                "value": True
            },
        ]
        message_ui_request.tags = {"config:": "environment variables"}
        return message_ui_request

    @classmethod
    def get_welcome_message(cls):
        agents_kickstart_help = agents_IP_tunnel_config
        agents_kickstart_help = agents_kickstart_help.replace('SomeAgentName1', cls.AGENT_NAMES[0])
        agents_kickstart_help = agents_kickstart_help.replace('SomeAgentName2', cls.AGENT_NAMES[1])

        message_ui_request = MsgUiDisplay()
        message_ui_request.fields = [{
            "type": "p",
            "value": agents_kickstart_help
        }, ]
        message_ui_request.tags = {"config:": "agents"}
        return message_ui_request

    # # # # # # # DESCRIBE THE MESSAGES FOR TT # # # # # # # # # # # # # #

    def _tt_message_testsuite_start(self, user_input):
        return MsgTestSuiteStart()

    def _tt_message_testsuite_abort(self, user_input):
        return MsgTestSuiteAbort()

    def _tt_message_testcase_start(self, user_input):
        return MsgTestCaseStart(testcase_id=self._current_tc)

    def _tt_message_testcase_restart(self, user_input):
        return MsgTestCaseRestart()

    def _tt_message_testcase_skip(self, user_input):
        return MsgTestCaseSkip()

    def _tt_message_step_verify_executed(self, user_input):
        logging.info("processing: %s | %s" % (user_input, type(user_input)))

        if type(user_input) is str and user_input.lower() == 'true':
            user_input = True
        elif type(user_input) is str and user_input.lower() == 'false':
            user_input = False
        elif type(user_input) is bool:
            pass
        else:
            logging.error("Couln't process user input %s" % user_input)
            return

        return MsgStepVerifyExecuted(
            response_type="bool",
            verify_response=user_input,
            # "node"= "coap_client",
            # "node_execution_mode": "user_assisted",
        )

    def _tt_message_step_stimuli_executed(self, user_input):

        return MsgStepStimuliExecuted(
            node="coap_client",
            node_execution_mode="user_assisted",
        )

    # # # # # # # DESCRIBE THE MESSAGES FOR GUI # # # # # # # # # # # # # #

    def _ui_request_testsuite_start(self, message_from_tt):
        message_ui_request = MsgUiRequestConfirmationButton(
            title="Do you want to start the TEST SUITE?"
        )
        message_ui_request.fields = [
            {
                "name": "ts_start",
                "type": "button",
                "value": True
            },
        ]
        return message_ui_request

    def _ui_request_testcase_start(self, message_from_tt):
        message_ui_request = MsgUiRequestConfirmationButton(
            title="Do you want to start the TEST CASE \n(%s)?" % self._current_tc
        )
        message_ui_request.fields = [
            {
                "name": "tc_start",
                "type": "button",
                "value": True
            },
        ]
        return message_ui_request

    def _ui_request_step_stimuli_executed(self, message_from_tt):
        message_ui_request = MsgUiRequestConfirmationButton(
            title="Do you confirm executing the STIMULI \n(%s)? " % self._current_step
        )
        message_ui_request.fields = [
            {
                "name": "stimuli_executed",
                "type": "button",
                "value": True
            },
        ]
        return message_ui_request

    def _ui_request_step_verification(self, message_from_tt):
        message_ui_request = MsgUiRequestConfirmationButton(
            title="Please VERIFY the information regarding the STEP \n(%s)" % self._current_step
        )
        message_ui_request.fields = [
            {
                "type": "p",
                "value": "Please provide VERIFY step response"
            },
            {
                "label": "OK",
                "name": "verify_executed",
                "type": "radio",
                "value": True
            },
            {
                "label": "Not OK",
                "name": "verify_executed",
                "type": "radio",
                "value": False
            },
        ]
        return message_ui_request


class OneM2MSessionMessageFactory(object):
    pass


class SixLoWPANSessionMessageFactory(object):
    pass


class CoMISessionMessageFactory(CoAPSessionMessageFactory):
    AGENT_NAMES = ['comi_client', 'comi_server']

    def __init__(self):
        super().__init__()


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


mapping_testsuite_to_message_factory = {
    'coap': CoAPSessionMessageFactory,
    'onem2m': OneM2MSessionMessageFactory,
    '6lowpan': SixLoWPANSessionMessageFactory,
    'comi': CoMISessionMessageFactory
}

DEFAULT_NODE_TO_USER_MAPPING = {
    'coap_client': '1',
    'coap_server': '2',
}


def main():
    try:
        amqp_exchange = str(os.environ['AMQP_EXCHANGE'])
    except KeyError:
        amqp_exchange = "amq.topic"

    try:
        amqp_url = str(os.environ['AMQP_URL'])
        print('Env vars for AMQP connection succesfully imported')

    except KeyError:
        amqp_url = "amqp://guest:guest@localhost/"

    logging.info('Using params: AMQP_URL=%s | AMQP_EXCHANGE=%s' % (amqp_url, amqp_exchange))

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "test_suite",
            help="Test suite name",
            choices=list(mapping_testsuite_to_message_factory.keys())
        )

        args = parser.parse_args()

    except Exception as e:
        print(e)

    try:
        message_factory = mapping_testsuite_to_message_factory[args.test_suite]()
    except KeyError:
        logging.error("Error launching test suite: %s" % args.test_suite)

    connection = pika.BlockingConnection(pika.URLParameters(amqp_url))
    channel = connection.channel()

    lock = threading.RLock()

    def ui_display_producer(lock, message, user_id=None, level=None):

        with lock:
            # build Message object if passed attribute is string
            if type(message) is str:
                message = message_factory.transform_string_to_ui_markdown_display(message)

            assert isinstance(message, Message), "didnt Message pass verifications"

            # set message route
            if user_id:
                message.routing_key = "ui.user.%s.display" % user_id
            elif hasattr(message, "node"):
                message.routing_key = "ui.user.%s.display" % DEFAULT_NODE_TO_USER_MAPPING['node']
            else:
                raise Exception('Not enough information to know where to route message')

            publish_message(connection, message)

            logging.info(
                "publishing: %s routing_key: %s" % (repr(message)[:STDOUT_MAX_STRING_LENGTH], message.routing_key))

    def ui_request_producer(lock, message, user_id=None):
        """

        :param message:
        :param request_name: Typically the field name of the button/file/etc
        :param user_id:
        :return:
        """

        with lock:
            # set message route
            if user_id:
                message.routing_key = "ui.user.%s.request" % user_id
                message.reply_to = "ui.user.%s.reply" % user_id
            elif hasattr(message, "node"):
                message.routing_key = "ui.user.%s.request" % DEFAULT_NODE_TO_USER_MAPPING['node']
                message.reply_to = "ui.user.%s.reply" % DEFAULT_NODE_TO_USER_MAPPING['node']
            else:
                raise Exception('Not enough information to know where to route message')

            publish_message(connection, message)

            logging.info("publishing:%s routing_key: %s correlation_id %s"
                         % (repr(message)[:STDOUT_MAX_STRING_LENGTH],
                            message.routing_key,
                            message.correlation_id))

            message_factory.add_pending_response(
                corr_id=message.correlation_id,
                request_message=message,
                requested_field_name_list=MessageFactory.get_field_keys_from_ui_request(message),
            )

    def on_message_received_from_ui(lock, message_received):
        with lock:
            logging.info("routing TT <- UI: %s | r_key: %s | corr_id %s"
                         % (repr(message_received)[:STDOUT_MAX_STRING_LENGTH],
                            message_received.routing_key,
                            message_received.correlation_id))

            # 0. print pending responses table
            message_factory.print_table_of_pending_messages()

            # 1. echo the some user's response to every user in session
            ui_display_producer(
                lock,
                message='User replied to request: %s' % repr(message_received.fields),
                level='debug',
                user_id='all'
            )

            # 2. Handle reply from user
            if message_factory.is_pending_response(message_received):

                logging.info('got reply to previous request, r_key: %s corr id %s, message %s'
                             % (
                                 message_received.routing_key,
                                 message_received.correlation_id,
                                 repr(message_received),
                             ))

                response_to_tt = message_factory.translate_ui_to_tt_message(message_received)

                # 3. Some replies are just confirmations , no chained TT actions associated to them
                if response_to_tt is None:
                    return

                logging.info("publishing:%s routing_key: %s"
                             % (repr(response_to_tt)[:STDOUT_MAX_STRING_LENGTH],
                                response_to_tt.routing_key))

                # 4. we have chained message for the TT
                publish_message(connection, response_to_tt)

            else:
                logging.info("Not in responses pending list. Duplication? Two users replied to same request?")

    def on_message_received_from_testing_tool(lock, message_received):
        with lock:
            logging.info("routing TT -> UI: %s | r_key: %s | corr_id %s"
                         % (repr(message_received)[:STDOUT_MAX_STRING_LENGTH],
                            message_received.routing_key,
                            message_received.correlation_id if hasattr(message_received, 'correlation_id') else None))

            # 0. update message factory states
            message_factory.update_state(message_received)

            # 1. echo message to user (if applicable)
            if type(message_received) not in MESSAGES_NOT_TO_BE_ECHOED:
                ui_display_message = message_factory.transform_message_to_ui_markdown_display(message_received)
                if ui_display_message:
                    ui_display_producer(lock, ui_display_message, 'all')  # TODO handle routing

            # 2. request input from user (if applicable)
            ui_request_message = message_factory.get_ui_request_action_message(message_received)
            if ui_request_message:
                ui_request_message = message_factory.tag_message(ui_request_message)
                ui_request_producer(lock, ui_request_message, 'all')  # TODO handle routing

    def get_lock_and_dispatch_tt_message(message):
        with lock:
            logging.debug("LOCK acquired")
            on_message_received_from_testing_tool(lock, message)
        logging.debug("LOCK released")

    def get_lock_and_dispatch_ui_message(message):
        with lock:
            logging.debug("LOCK acquired")
            on_message_received_from_ui(lock, message)
        logging.debug("LOCK released")

    tt_amqp_listener_thread = AmqpListener(
        amqp_url=amqp_url,
        amqp_exchange=amqp_exchange,
        topics=TESTING_TOOL_TOPIC_SUBSCRIPTIONS,
        callback=get_lock_and_dispatch_tt_message)

    ui_amqp_listener_thread = AmqpListener(
        amqp_url=amqp_url,
        amqp_exchange=amqp_exchange,
        topics=UI_REPLY_TOPICS,
        callback=get_lock_and_dispatch_ui_message)

    tt_amqp_listener_thread.setName('TT_listener_thread')
    ui_amqp_listener_thread.setName('UI_listener_thread')

    tt_amqp_listener_thread.start()
    ui_amqp_listener_thread.start()

    logging.info('ui connector started listening to the event bus..')

    ui_request_producer(lock, message_factory.get_amqp_url_connection_message(), 'all')
    ui_display_producer(lock, message_factory.get_welcome_message(), 'all')

    tt_amqp_listener_thread.join()
    ui_amqp_listener_thread.join()

    logging.info('ui adaptor stopping..')


if __name__ == '__main__':
    main()
