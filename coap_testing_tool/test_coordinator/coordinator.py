# -*- coding: utf-8 -*-
#!/usr/bin/env python3

from asyncio import log
from collections import OrderedDict
from kombu import Connection, Exchange, Queue, Producer
from kombu.mixins import ConsumerMixin
from itertools import cycle
from enum import Enum
from coap_testing_tool.utils.exceptions import TatError, SnifferError,CoordinatorError, AmqpMessageError
from coap_testing_tool.utils.amqp_synch_call import AmqpSynchronousCallClient
import yaml, os, json
import requests
import base64
import errno
import traceback
from coap_testing_tool.test_coordinator.webserver import HTTPServer,HTTPServer_RequestHandler
from coap_testing_tool.test_coordinator.logger import *



from multiprocessing import Process


# TODO these VARs need to come from the session orchestrator + test configuratio files
COAP_CLIENT_IUT_MODE =  'user-assisted'
COAP_SERVER_IUT_MODE = 'automated'
ANALYSIS_MODE = 'post_mortem' # either step_by_step or post_mortem


# component identification & bus params
COMPONENT_ID = 'test_coordinator'
COMPONENT_DIR = 'coap_testing_tool/test_coordinator'
DEFAULT_PLATFORM = "127.0.0.1:15672"
DEFAULT_EXCHANGE = "default"


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# TODO delete after AMQP interfaces implemented
API_TAT = "http://127.0.0.1:2080"
API_SNIFFER = "http://127.0.0.1:8081"
SNIFFER_PARAMS = ('udp port 5683', 'lo0')

# folders testcases, logs and data
TMPDIR = os.path.join( os.getcwd(), COMPONENT_DIR, 'tmp')
DATADIR = os.path.join( os.getcwd(), COMPONENT_DIR, 'data')
LOGDIR = os.path.join( os.getcwd(), COMPONENT_DIR, 'log')
TD_DIR = os.path.join( os.getcwd(), COMPONENT_DIR, 'teds')

# set temporarilly as default TODO get this from finterop session context!
TD_COAP = os.path.join(TD_DIR,"TD_COAP_CORE.yaml")

# Other API params
#from webserver import API_TAT,API_SNIFFER


# - - - AUX functions - - - - -

def list_to_str(ls):
    """
    flattens a nested list up to two levels of depth

    :param ls:
    :return: single string with all the items inside the list
    """

    ret = ''
    for l in ls:
        if isinstance(l,list):
            for sub_l in l:
                if isinstance(sub_l,list):
                    # I truncate in the second level
                    pass
                else:
                    ret += sub_l +' \n '
        else:
            ret += l +' \n '
    return ret




# - - - - YAML parser aux classes and methods - - - -

def testcase_constructor(loader, node):
    instance = TestCase.__new__(TestCase)
    yield instance
    state = loader.construct_mapping(node, deep=True)
    #print("pasing test case: " + str(state))
    instance.__init__(**state)

yaml.add_constructor(u'!testcase', testcase_constructor)

# def yaml_include(loader, node):
#     # Get the path out of the yaml file
#     file_name = os.path.join(os.path.dirname(loader.name), node.value)
#
#     with open(file_name) as inputfile:
#         return yaml.load(inputfile)
#
# yaml.add_constructor("!include", yaml_include)
# yaml.add_constructor(u'!configuration', testcase_constructor)


def import_teds(yamlfile):
    """
    TODO implement specif import for configs? or use the same?

    :param yamlfile:
    :return: list of imported test cases objects
    """
    td_list = []
    with open(yamlfile, "r", encoding="utf-8") as stream:
        yaml_docs = yaml.load_all(stream)
        for yaml_doc in yaml_docs:
             if type(yaml_doc) is TestCase:
                 logging.info(' Parsed test case: %s from yaml file: %s :'%(yaml_doc.id,yamlfile) )
                 td_list.append(yaml_doc)
        #         for s in yaml_doc.sequence:
        #             logging.info(' \t Parsed test case step %s :' % s)

    return td_list


class Verdict:
    """

    Known verdict values are:
     - 'none': No verdict set yet
     - 'pass': The NUT fulfilled the test purpose
     - 'inconclusive': The NUT did not fulfill the test purpose but did not display
                 bad behaviour
     - 'fail': The NUT did not fulfill the test purpose and displayed a bad
               behaviour
     - 'aborted': The test execution was aborted by the user
     - 'error': A runtime error occured during the test

    At initialisation time, the verdict is set to None. Then it can be updated
    one or multiple times, either explicitely calling set_verdict() or
    implicitly if an unhandled exception is caught by the control module
    (error verdict) or if the user interrupts the test manually (aborted
    verdict).

    Each value listed above has precedence over the previous ones. This means
    that when a verdict is updated, the resulting verdict is changed only if
    the new verdict is worse than the previous one.
    """

    __values = ('none', 'pass', 'inconclusive', 'fail', 'aborted', 'error')

    def __init__(self, initial_value: str = None):
        """
        Initialize the verdict value to 'none' or to the given value

        :param initial_value: The initial value to put the verdict on
        :type initial_value: optional(str)
        """
        self.__value = 0
        self.__message = ''
        if initial_value is not None:
            self.update(initial_value)

    def update(self, new_verdict: str, message: str = ''):
        """
        Update the verdict

        :param new_verdict: The name of the new verdict value
        :param message: The message associated to it
        :type new_verdict: str
        :type message: str
        """
        assert new_verdict in self.__values

        new_value = self.__values.index(new_verdict)
        if new_value > self.__value:
            self.__value = new_value
            self.__message = message

    @classmethod
    def values(cls):
        """
        List the known verdict values

        :return: The known verdict values
        :rtype: (str)
        """
        return cls.__values

    def get_value(self) -> str:
        """
        Get the value of the verdict

        :return: The value of the verdict as a string
        :rtype: str
        """
        return self.__values[self.__value]

    def get_message(self) -> str:
        """
        Get the last message update of this verdict

        :return: The last message update
        :rtype: str
        """
        return self.__message


    def __str__(self) -> str:
        """
        Get the value of the verdict as string for printing it

        :return: The value of the verdict as a string
        :rtype: str
        """
        return self.__values[self.__value]


class Iut:
    def __init__(self, node = None, mode="user_assisted"):
        # TODO get IUT mode from session config!!!
        self.node = node
        if mode:
            assert mode in ("user_assisted", "automated")
        self.mode = mode

    def to_dict(self):
        ret = OrderedDict({'iut':self.node})
        ret.update({'iut_mode':self.mode})
        return ret


    # TODO implement this
    def configure(self):
        pass

    def __repr__(self):
        if self.mode:
            return "%s(node=%s, mode=%s)" % (self.__class__.__name__, self.node, self.mode if self.mode else "not defined..")
        return "%s(node=%s)" % (self.__class__.__name__, self.node)

class Config:
     def __init__(self,config_id, uri, sniffers_configs, topology, description):
        pass
        #TBD

class Step():

    # TODO check step id uniqueness
    def __init__(self, step_id, type, description, iut=None):
        self.id = step_id
        assert type in ("stimuli","check","verify")
        # TODO sth else might need to be defined for conformance testing TBD (inject? drop packet?)..
        self.type = type
        self.description = description

        # stimuli and verify step MUST have a iut field in the YAML file
        if type=='stimuli' or type=='verify':
            assert iut is not None
            self.iut = Iut(iut)

            # Check and verify steps need a partial verdict
            self.partial_verdict = Verdict()
        else:
            self.iut = None

        self.state = None



    def __repr__(self):
        node = ''
        mode = ''
        if self.iut is not None:
            node = self.iut.node
            mode =  self.iut.mode
        return "%s(step_id=%s, type=%s, description=%s, iut node=%s, iut mode =%s)" \
               %(self.__class__.__name__, self.id, self.type, self.description, node , mode)

    def reinit(self):

        if self.type in ('check','verify'):
            self.partial_verdict = Verdict()

            # when using post_mortem analysis mode all checks are postponed , and analysis is done at the end of the TC
            logging.debug('Processing step init, step_id: %s, step_type: %s, ANALYSIS_MODE is %s' % (
            self.id, self.type, ANALYSIS_MODE))
            logging.debug(self.type == 'check' and ANALYSIS_MODE == 'post_mortem')
            if self.type == 'check' and ANALYSIS_MODE == 'post_mortem':
                self.change_state('postponed')
            else:
                self.change_state(None)
        else: #its a stimuli
            self.change_state(None)

    def to_dict(self, verbose = None):
        step_dict = OrderedDict()
        step_dict['step_id'] = self.id
        if verbose:
            step_dict['step_type'] = self.type
            step_dict['step_info'] = self.description
            step_dict['step_state'] = self.state
            # it the step is a stimuli then lets add the IUT info(note that checks dont have that info)
            if self.type == 'stimuli' or self.type == 'verify':
                step_dict.update(self.iut.to_dict())
        return step_dict

    def change_state(self,state):
        # postponed state used when checks are postponed for the end of the TC execution
        assert state in (None,'executing','finished','postponed')
        self.state = state
        logging.info('Step %s state changed to: %s'%(self.id,self.state))

    def set_result(self,result,result_info):
        # Only check and verify steps can have a result
        assert self.type in ('check','verify')
        assert result in Verdict.values()
        self.partial_verdict.update(result,result_info)

class TestCase():
    """
    FSM:
    (None,'skipped', 'executing','ready_for_analysis','analyzing','finished')
    None -> Rest state
    Skipped -> Nothing to do here, just skip this TC
    Executing -> Executing intermediary states (executing steps, partial analysis for check steps -if active testing-, executing verify steps)
    Analyzing -> Either TAT analysing PCAP -post_mortem type- or processing all partial verdicts from check steps -step_by_step-
    Finished -> all steps finished, all checks analyzed, and verdict has been emitted

    ready_for_analysis -> intermediate state between executing and analyzing for waiting for user call to analyse TC
    """

    def __init__(self, testcase_id , uri, objective, configuration, references, pre_conditions, sequence ):
        self.id = testcase_id
        self.state = None
        self.uri = uri
        self.objective = objective
        self.configuration_id = configuration
        self.references = references
        self.pre_conditions = pre_conditions
        self.sequence=[]
        for s in sequence:
            # TODO add more sanity checks
            try:
                assert "step_id" and "description" and "type" in s
                if s['type']=='stimuli':
                    assert "iut" in s
                self.sequence.append(Step(**s))
            except:
                logging.error("Error found while trying to parse: %s" %str(s))
                raise
        self._step_it = iter(self.sequence)
        self.current_step = None
        self.report = None

        # TODO if ANALYSIS is post mortem change all check step states to postponed at init!

    def reinit(self):
        """
        - prepare test case to be re-executed
        - brings to state zero variables that might have changed during a previous execution
        :return:
        """
        self.state = None
        self.current_step = None
        self._step_it = iter(self.sequence)

        for s in self.sequence:
            s.reinit()


    def __repr__(self):
        return "%s(testcase_id=%s, uri=%s, objective=%s, configuration=%s, test_sequence=%s)" % (self.__class__.__name__, self.id ,
         self.uri, self.objective, self.configuration_id,self.sequence)

    def to_dict(self,verbose=None):

        d = OrderedDict()
        d['testcase_id'] = self.id

        if verbose:
            d['testcase_ref'] = self.uri
            d['objective'] = self.objective
            d['state'] = self.state

        return d

    def seq_to_dict(self):
        steps = []
        for step in self.sequence:
            steps.append(step.to_dict())
        return steps

    def change_state(self,state):
        assert state in (None,'skipped', 'executing','ready_for_analysis','analyzing','finished')
        self.state = state
        logging.info('Testcase %s changed state to %s'%(self.id, state))

    def check_all_steps_finished (self):
        it = iter(self.sequence)
        step = next(it)

        try:
            while True:
                # check that there's no steps in state = None or executing
                if step.state is None or step.state == 'executing':
                    logging.debug("[TESTCASE] - there are still steps to execute or under execution")
                    return False
                else:
                    step = it.__next__()
        except StopIteration:
            logging.debug("[TESTCASE] - all steps are either finished or pending (waiting for analysis)")
            return True

    def generate_final_verdict(self,tat_analysis_report_a_posteriori=None):
        """
        Generates the final verdict and report taking into account the CHECKs and VERIFYs of the testcase
        :return: tuple: (final_verdict, verdict_description, tc_report) ,
                 where final_verdict in ("None", "error", "inconclusive","pass","fail")
                 where description is String type
                 where tc report is a list :
                                [(step, step_partial_verdict, step_verdict_info, associated_frame_id (can be null))]
        """
        # TODO hanlde frame id associated to the step , used for GUI purposes
        assert self.check_all_steps_finished()

        final_verdict = Verdict()
        tc_report = []
        logging.debug("[VERDICT GENERATION] starting the verdict generation")
        for step in self.sequence:
            # for the verdict we use the info in the checks and verify steps
            if step.type in ("check","verify"):

                logging.debug("[VERDICT GENERATION] Processing step %s" %step.id)

                if step.state == "postponed":
                    tc_report.append((step.id, None, "%s postponed" %step.type.upper(), ""))
                elif step.state == "finished":
                    tc_report.append((step.id, step.partial_verdict.get_value(), step.partial_verdict.get_message(),""))
                    # update global verdict
                    final_verdict.update(step.partial_verdict.get_value(),step.partial_verdict.get_message())
                else:
                    msg="step %s not ready for analysis"%(step.id)
                    logging.error("[VERDICT GENERATION] " + msg)
                    raise CoordinatorError(msg)

        # append at the end of the report the analysis done a posteriori (if any)
        if tat_analysis_report_a_posteriori:
            for item in tat_analysis_report_a_posteriori:
                # TODO process the items correctly
                tc_report.append(item)
                final_verdict.update(item[1], item[2])

        if final_verdict.get_value() == 'pass':
            final_verdict.__message = 'Test case executed correctly'

        return final_verdict.get_value(), final_verdict.get_message(), tc_report


class Coordinator(ConsumerMixin):
    """
    F-Interop API
    source:  http://doc.f-interop.eu/#services-provided
    |[*testcoordination.testsuite.getstatus*](#testcoordination-testsuite-getstatus) | Message for debugging purposes. The coordination component returns the status of the execution |
    |[*testcoordination.testsuite.gettestcases*](#testcoordination-gettestcases) | Message for requesting the list of test cases included in the test suite.|
    |[*testcoordination.testsuite.start*](#testcoordination-testsuite-start) | Message for triggering start of test suite. The command is given by one of the users of the session.|
    |[*testcoordination.testsuite.abort*](#testcoordination-testsuite-abort)| Message for aborting the ongoing test session.|
    |[*testcoordination.testcase.skip*](#testcoordination-testcase-skip) | Message for skipping a test case. Coordinator passes to the next test case if there is any left.|
    |[*testcoordination.testcase.select*](#testcoordination-testcase-select) | Message for selecting next test case to be executed. Allows the user to relaunch an already executed test case.|
    |[*testcoordination.testcase.start*](#testcoordination-testcase-start) | Message for triggering the start of the test case. The command is given by one of the users of the session.|
    |[*testcoordination.testcase.restart*](#testcoordination-testcase-restart) | Message for triggering the restart of a test case (TBD any of the participants MAY send this?)|
    |[*testcoordination.testcase.finish*](#testcoordination-testcase-finish) |  Message for triggering the end of a test case. This command is given by one of the users of the session.|
    |[*testcoordination.step.finished*](#testcoordination-step-finished) | Message for indicating to the coordinator that the step has already been executed.|
    |[*testcoordination.step.stimuli.executed*](#testcoordination-step-stimuli-executed)| Message pushed by UI or agent indicating the stimuli was executed.|
    |[*testcoordination.step.check.response*](#testcoordination-step-check-response)| TBD  (for step_by_step analysis).|
    |[*testcoordination.step.verify.response*](#testcoordination-step-verify-response)| Message pushed by UI or agent providing the response to verify step.|

    """


    def __init__(self, amqp_connection, ted_file):
        # import TEDs (test extended descriptions), the import_ted "builds" the test cases
        imported_docs = import_teds(ted_file)
        self.teds=OrderedDict()
        for ted in imported_docs:
            self.teds[ted.id]=ted
        # test cases iterator (over the TC objects, not the keys)
        self._ted_it = cycle(self.teds.values())
        self.current_tc = None

        # queues & default exchange declaration
        self.connection = amqp_connection
        self.exchange = Exchange(DEFAULT_EXCHANGE, type="topic", durable=True)
        self.control_queue = Queue("control.testcoordination.service@{name}".format(name=COMPONENT_ID),
                                   exchange=self.exchange,
                                   routing_key='control.testcoordination',
                                   durable=False)

        self.producer = self.connection.Producer(serializer='json')

        self.producer.publish(
            body = json.dumps({"_type":'testcoordination.info',
                               'message':'Test Coordinator is up!'}),
            routing_key='control.testcoordination.info',
            exchange=self.exchange
        )

    def get_consumers(self, Consumer, channel):
        return [
            Consumer(queues=[self.control_queue],
                     callbacks=[self.handle_control],
                     no_ack=True,
                     accept=['json']),
        ]

    def on_consume_ready(self, connection, channel, consumers, wakeup=True, **kwargs):
        log.info("Ready")

    def handle_control(self, body, message):


        ###### AUXILIAR MESSAGING FUNCTIONS #####

        def amqp_reply(orig_message, response):

            # check first that sender didnt forget about reply to and corr id
            try:
                orig_message.properties['reply_to']
                orig_message.properties['correlation_id']
            except KeyError:
                logging.error(msg='There is an error on the request, either reply_to or correlation_id not provided')
                return

            self.producer.publish(response, exchange=self.exchange,
                             routing_key=orig_message.properties['reply_to'],
                             correlation_id=orig_message.properties['correlation_id']
                                  )
            message.ack()

        def notify_current_testcase():
            # testcoordination notification
            coordinator_notif = OrderedDict()
            coordinator_notif.update({'_type': 'testcoordination.testcase.next'})
            coordinator_notif.update({'message': 'Next test case to be executed is %s' % self.current_tc.id})
            coordinator_notif.update(self.current_tc.to_dict(verbose = True))


            self.producer.publish(
                body=json.dumps(coordinator_notif),
                routing_key='control.testcoordination.testcase',
                exchange=self.exchange
            )

        def notify_current_step_execute():
            # testcoordination notification
            coordinator_notif = OrderedDict()
            coordinator_notif.update({'_type': 'testcoordination.step.execute'})
            coordinator_notif.update({'message': 'Next test step to be executed is %s' % self.current_tc.current_step.id})
            coordinator_notif.update(self.current_tc.current_step.to_dict(verbose = True))

            self.producer.publish(
                body=json.dumps(coordinator_notif),
                routing_key='control.testcoordination.step',
                exchange=self.exchange
            )

        def notify_coordination_error( message, error_code):
            # testcoordination.error notification
            # TODO error codes?
            coordinator_notif = OrderedDict()
            coordinator_notif.update({'_type': 'testcoordination.error',})
            coordinator_notif.update({'message': message,})
            coordinator_notif.update({'error_code' : error_code,})

            self.producer.publish(
                body=json.dumps(coordinator_notif),
                routing_key='control.testcoordination.error',
                exchange=self.exchange
            )


        ### EVENT HANDLING ###

        logging.debug('event received on the queue: %s || %s' % (body, message))

        # TODO check malformed messages first
        event = json.loads(body)
        event_type = event['_type']

        #prepare response
        response = OrderedDict()

        if event_type == "testcoordination.testsuite.gettestcases":

            # this is a request so I answer directly on the message
            testcases = self.get_test_cases_basic(verbose=True)
            response.update({'_type' : event_type})
            response.update({'ok':True})
            response.update(testcases)
            amqp_reply(message,json.dumps(response))


        elif event_type == "testcoordination.testsuite.getstatus":

            status = self.states_summary()
            # this is a request so I answer directly on the message
            response.update({'_type' : event_type})
            response.update({'ok':True})
            response.update({'status': status})
            amqp_reply(message,json.dumps(response))

        elif event_type == "testcoordination.testcase.skip":

            # if no testcase_id was sent then I skip  the current one
            try:
                testcase_skip = event['testcase_id']
            except KeyError:
                testcase_skip = self.current_tc.id

            # change tc state to 'skipped'
            testcase_t = self.get_testcase(testcase_skip)
            testcase_t.change_state("skipped")

            # response ok
            response.update({'_type' : event_type})
            response.update({'ok':True})
            amqp_reply(message, json.dumps(response))

            # if skipped tc is current test case then next tc
            if testcase_skip == self.current_tc.id:
                self.next_test_case()
                notify_current_testcase()


        elif event_type == "testcoordination.testsuite.start":
            # TODO in here maybe launch the enxt configuration of IUT
            # TODO maybe return next test case
            # TODO reboot automated IUTs
            # TODO open tun interfaces in agents
            # response ok
            response.update({'_type' : event_type})
            response.update({'ok':True})
            amqp_reply(message, response)

            # send general notif
            notify_current_testcase()

        elif event_type == "testcoordination.testcase.select":

            # assert and get testcase_id from message
            try:
                # jump to selected tc
                self.select_test_case(event['testcase_id'])
            except KeyError:
                error_msg = "Incorrect or empty testcase_id"
                # response not ok
                response.update({'_type': event_type})
                response.update({'ok': False})
                response.update({'message' : error_msg})
                amqp_reply(message, response)
                # send general notif
                notify_coordination_error(message=error_msg,error_code=None)
            except CoordinatorError as e:
                error_msg = e.message
                # response not ok
                response.update({'_type': event_type})
                response.update({'ok': False})
                response.update({'message': error_msg})
                amqp_reply(message, response)
                # send general notif
                notify_coordination_error(message=error_msg, error_code=None)


            #response ok
            response.update({'_type' : event_type})
            response.update({'ok':True})
            amqp_reply(message, response)

            # send general notif
            notify_current_testcase()


        elif event_type == "testcoordination.testcase.start":

            if self.current_tc is None:
                error_msg = "No testcase selected"

                # response not ok
                response.update({'_type': event_type})
                response.update({'ok': False})
                response.update({'message': error_msg})
                amqp_reply(message, response)

                # notify all
                notify_coordination_error(message =error_msg, error_code=None)
                return

            # TODO handle configuration phase before execution!
            self.start_test_case()
            # response ok
            response.update({'_type' : event_type})
            response.update({'ok':True})
            amqp_reply(message, response)

            # send general notif
            notify_current_step_execute()


        elif event_type == "testcoordination.testsuite.start":
            # TODO only enter if current_ tc = None
            self.start_test_suite()

            # response ok
            response.update({'_type' : event_type})
            response.update({'ok':True})
            amqp_reply(message, response)

            # send general notif
            notify_current_testcase()


        elif event_type == "testcoordination.step.stimuli.executed":
            # TODO verify source if of message?
            self.process_stimuli_step_executed()

            # response ok
            response.update({'_type' : event_type})
            response.update({'ok':True})
            amqp_reply(message, response)

            # pass to next step
            if self.next_step():
                notify_current_step_execute()
            else:
                self.finish_test_case()

        elif event_type == "testcoordination.step.verify.response":

            # assert and get testcase_id from message
            try:
                verify_response = event['verify_response']
            except KeyError:
                error_msg = "Verify_response field needs to be provided"
                # response not ok
                response.update({'_type': event_type})
                response.update({'ok': False})
                response.update({'message': error_msg})
                amqp_reply(message, response)
                # send general notif
                notify_coordination_error(message=error_msg, error_code=None)


            self.process_verify_step_response(verify_response)

            # response ok
            response.update({'_type' : event_type})
            response.update({'ok':True})
            amqp_reply(message, response)

            # pass to next step
            if self.next_step():
                notify_current_step_execute()
            else:
                self.finish_test_case()


        elif event_type == "testcoordination.step.check.response":
            # This is call is just used when we have step_by_step analysis mode
            assert ANALYSIS_MODE == 'step_by_step'

            try:
                verdict = event['partial_verdict']
                description = event['description']
            except KeyError:
                notify_coordination_error(message='Malformed CHECK response', error_code=None)

            self.process_check_step_response(verdict,description)

            # response ok
            response.update({'_type' : event_type})
            response.update({'ok':True})
            amqp_reply(message, response)

            # pass to next step
            if self.next_step():
                notify_current_step_execute()
            else:
                self.finish_test_case()

        elif event_type == "testcoordination.testcase.finish":
            self.finish_test_case()

            # response ok
            response.update({'_type' : event_type})
            response.update({'ok':True})
            amqp_reply(message, response)

            # send general notif
            notify_current_testcase()

        else:
            notify_coordination_error(message='Cannot dispatch event_type %s'%event_type , error_code=None)

        logging.info('Event handled, response sent through the bus: %s'%(json.dumps(response)))

    # # Call to other components methods
    # # TODO this should be implement using events..
    # def sniffer_clear(self):
    #     sniffer_url = API_SNIFFER + '/sniffer_api/finishSniffer'
    #
    #     # Finish sniffer, the goal here is to clear unfinished test sessions
    #     try:
    #         r = requests.post(sniffer_url)
    #         logging.info( self.log_message("Content of the response on %s call is %s", sniffer_url, r.content))
    #     except:
    #         raise CoordinatorError( "Sniffer API doesn't respond on %s, maybe it isn't up yet" % sniffer_url)

    def get_test_cases_basic(self, verbose = None):

        resp = []
        for tc_v in self.teds.values():
            resp.append(tc_v.to_dict(verbose))
        # If no test case found
        if len(resp) == 0:
            raise CoordinatorError("No test cases found")

        return {'tc_list' : resp}

    def get_test_cases_list(self):
        return list(self.teds.keys())

    #def select_testcases(self, tc_id):

    def select_test_case(self,params):
        """
        this is more like a jump to function rather than select
        :param params: test case id
        :return: dict repr of the selected testcase if found
        :raises: CoordinatorError when test case not found
        """
        tc_id = params
        if tc_id in list(self.teds.keys()):
            self.current_tc = self.teds[tc_id]
            # in case is was already executed once
            self.current_tc.reinit()
            logging.debug("Test case selected to be executed: %s" %self.current_tc.id)
            return self.current_tc.to_dict(verbose=True)
        else:
            logging.error( "%s not found in : %s "%(tc_id,self.teds))
            raise CoordinatorError('Testcase not found')


    def start_test_suite(self):
        """
        :return: test case to start with
        """

        try:
            # resets all previously executed TC
            for tc in self.teds.values():
                tc.reinit()
            # init testcase if None
            if self.current_tc is None:
                self.next_test_case()
            return self.current_tc
        except:
            raise


    def start_test_case(self):
        """
        :return: next step to be executed
        """
        global API_SNIFFER
        global SNIFFER_PARAMS


        # TODO get filter from config of the TEDs
        par = {
            'testcase_id': self.current_tc.id[:-4],
            'filter': SNIFFER_PARAMS[0],
            'interface': SNIFFER_PARAMS[1],
        }

        # TODO implement in separate method & handle it with RMQ messages
        # sniffer_url = API_SNIFFER + '/sniffer_api/launchSniffer'
        # try:
        #     r = requests.post(sniffer_url, params=par)
        #     logging.info(
        #         "Content of the response on %s call with %s is %s",
        #         sniffer_url,
        #         par,
        #         r.content
        #     )
        # except Exception as e:
        #     raise SnifferError("Sniffer API doesn't respond, maybe it isn't up yet? \n Exception thrown %s"%str(e))

        try:
            # init testcase and step and their states if they are None
            if self.current_tc is None:
                self.next_test_case()
            if self.current_tc.current_step is None:
                self.next_step()
            self.current_tc.change_state('executing')

            return self.execute_step()
        except:
            raise


    def process_verify_step_response(self, verify_response):
        assert verify_response is not None


        if verify_response == True:
            self.current_tc.current_step.set_result("pass",
                                                    "VERIFY step: User informed that the information was displayed "
                                                    "correclty on his/her IUT")
        elif verify_response == False :
            self.current_tc.current_step.set_result("fail",
                                                    "VERIFY step: User informed that the information was not displayed"
                                                    " correclty on his/her IUT")
        else:
            self.current_tc.current_step.set_result("error",'Malformed verify response from GUI')
            raise CoordinatorError('Malformed VERIFY response')

        self.current_tc.current_step.change_state('finished')

        # some info logs:
        logging.debug("[step_finished event] step %s, type %s -> new state : %s"
                      %(self.current_tc.current_step.id,
                        self.current_tc.current_step.type,
                        self.current_tc.current_step.state))


    def process_check_step_response(self, verdict, description):
        # some sanity checks on the states
        assert self.current_tc is not None
        assert self.current_tc.state is not None
        assert self.current_tc.current_step is not None

        #sanity checks on the passed params
        assert verdict is not None
        assert description is not None
        assert verdict.lower() in Verdict.__values

        self.current_tc.current_step.set_result(verdict.lower(), "CHECK step: %s" % description)
        self.current_tc.current_step.change_state('finished')

        # some info logs:
        logging.debug("[step_finished event] step %s, type %s -> new state : %s"
                      %(self.current_tc.current_step.id,
                        self.current_tc.current_step.type,
                        self.current_tc.current_step.state))


    def process_stimuli_step_executed(self):
        """
        :return: dict of the next step to be executed
        """

        # some sanity checks on the states
        assert self.current_tc is not None
        assert self.current_tc.state is not None
        assert self.current_tc.current_step is not None
        assert self.current_tc.current_step.state == 'executing'

        # step state ->finished
        self.current_tc.current_step.change_state('finished')

        # some info logs:
        logging.debug("[step_finished event] step %s, type %s -> new state : %s"
                      %(self.current_tc.current_step.id,
                        self.current_tc.current_step.type,
                        self.current_tc.current_step.state))


    #TODO internal use of the coordinator or should be added to the API calls?
    def finish_test_case(self):
        """

        :return:
        """
        assert self.current_tc.check_all_steps_finished()

        global API_SNIFFER
        global API_TAT

        # get TC params
        #tc_id = self.current_tc.id
        tc_id = self.current_tc.id[:-4]
        tc_ref = self.current_tc.uri

        self.current_tc.change_state('analyzing')
        # Finish sniffer and get PCAP
        # TODO first tell sniffer to stop!

        if ANALYSIS_MODE == 'post_mortem' :

            amqp_rpc_client = AmqpSynchronousCallClient(component_id=COMPONENT_ID)
            body = {'_type':'sniffing.getCapture','testcase_id': tc_id}
            try:
                ret = amqp_rpc_client.call(routing_key ="control.sniffing.service", body= body)
                logging.info("Content of the response on the sniffing.getCapture call is %s" %(str(ret)))
            except Exception as e:
                raise SnifferError("Sniffer API doesn't respond on %s, maybe it isn't up yet \n Exception info%s"
                                   %(str(ret),str(e)))

            # let's try to save the file and then push it to results repo
            # TODO push PCAP to results repo
            pcap_file_base64 = ''
            try:
                pcap_file_base64 = ret['value']
                filename = ret['filename']
                # save to file
                with open(os.path.join(TMPDIR, filename), "wb") as pcap_file:
                    nb = pcap_file.write(base64.b64decode(pcap_file_base64))
                    logging.info("Pcap correctly saved %dB at %s from sniffer" % (nb, TMPDIR))
            except Exception as e:
                raise CoordinatorError("Cannot decode received PCAP received from sniffer \n Exception info: %s "
                                       %(str(e)))


            # Forwards PCAP to TAT API
            body = {
                '_type': 'analysis.testCaseAnalyze',
                'testcase_id': tc_id,
                "testcase_ref": tc_ref,
                "filetype":"pcap_base64",
                "filename":tc_id+".pcap",
                "value":pcap_file_base64
            }

            tat_response = amqp_rpc_client.call(routing_key="control.analysis.service", body=body)
            logging.info("Response received from TAT: %s " % (tat_response))

            # TODO check if the response is ok first, else raise an error

            # Save the json object

            json_save = os.path.join(
                TMPDIR,
                tc_id + '.json'
            )
            try:
                with open(json_save, 'w') as f:
                    json.dump(tat_response, f)
            except:
                CoordinatorError("Couldn't write the json file")

        # TODO for BOTH post_mortem analysis & step_by_step push PCAP(s) to results repo

        # let's process the partial verdicts from TAT's answer
        # they come as [[str,str]] first string is partial verdict , second is description.
        partial_verd = []
        step_count = 0
        for item in tat_response['partial_verdicts']:
            # I cannot really know which partial verdicts belongs to which step cause TAT doesnt provide me with this
            # info, so ill make a name up(this is just for visualization purposes)
            step_count += 1
            p = ("A_POSTERIORI_CHECK_%d"%step_count, item[0] , item[1])
            partial_verd.append(p)
            logging.debug("partial verdict received from TAT: %s"%str(p))

        # generates a general verdict considering other steps partial verdicts besides TAT's
        gen_verdict, gen_description, report = self.current_tc.generate_final_verdict(partial_verd)

        # overwrite for generating final verdict, description and report, the rest of the fields keep them unchanged

        assert type(tat_response) is dict
        overridden_response = tat_response
        overridden_response['verdict'] = gen_verdict
        overridden_response['description'] = gen_description
        overridden_response['partial_verdicts'] = report


        # lets generate test case report
        self.current_tc.report=[]
        for item in overridden_response:
            self.current_tc.report.append(item)


        logging.info("General verdict generated: %s" %str(self.current_tc.report))
        # pass to the next testcase
        # tc = self.next_test_case()

        # if tc:
        #     information = OrderedDict()
        #     information['_type'] = 'information'
        #     information['next_test_case'] = tc.id
        #     ret.append(information)
        # else:
        #     information = OrderedDict()
        #     information['_type'] = 'information'
        #     information['next_test_case'] = None
        #     ret.append(information)
        #
        # logging.info("sending response to GUI " + json.dumps(ret))

        return self.current_tc.report


    def next_test_case(self):
        """
        circular iterator over the testcases returns only not yet executed ones
        :return: current test case (Tescase object) or None if nothing else left to execute
        """

        # _ted_it is acircular iterator
        # testcase can eventually be executed out of order due tu user selection-
        self.current_tc = next(self._ted_it)
        max_iters = len(self.teds)

        # get next not executed nor skipped testcase
        while self.current_tc.state is not None:
            self.current_tc = self._ted_it.__next__()
            max_iters -= 1
            if max_iters < 0:
                self.current_tc = None
                return None

        return self.current_tc

    def next_step(self):
        """
        Simple iterator over the steps.
        Starts the TC if current_TC is None
        :return: step or None if testcase finished

        """
        if self.current_tc is None:
            self.next_test_case()
        try:
            self.current_tc.current_step = next(self.current_tc._step_it)

            # skip postponed steps
            while self.current_tc.current_step.state == 'postponed':
                self.current_tc.current_step = next(self.current_tc._step_it)

        except StopIteration:
            logging.info('Test case finished. No more steps to execute in testcase: %s' %self.current_tc.id)
            # return None when TC finished
            return None

        logging.info('Next step to execute: %s'%self.current_tc.current_step.id)

        return self.current_tc.current_step

    def execute_step(self):
        """
        Notes:
            stimulis: are executed by the IUTs - either user-assisted-iut(print in GUI) or automated IUTs
            (agents receive the step_id and they interface with the IUTs somehow)
            checks: are executed by the TATs either in an active mode(in a synchronous way)
            or passive -at the end of the testcase-
            verify: idem as stimulis, the difference is that we receive an answer when executing these steps

        :returns: current step
        """

        # if self.current_tc.current_step is None:
        #     self.next_step()

        assert self.current_tc.current_step is not None

        if self.current_tc.current_step.type == "stimuli":
            self.current_tc.current_step.change_state('executing')

        elif self.current_tc.current_step.type == "verify":
            self.current_tc.current_step.change_state('executing')

        elif self.current_tc.current_step.type == "check":
            if ANALYSIS_MODE == 'step_by_step':
                self.current_tc.current_step.change_state('executing')
            elif ANALYSIS_MODE == 'post_mortem':
                self.current_tc.current_step.change_state('postponed')
            else:
                CoordinatorError(message='ANALYSIS_MODE expected step_by_step or post_mortem, but %s found'%ANALYSIS_MODE)

        return self.current_tc.current_step

    def states_summary(self):
        summ=[]
        if self.current_tc:
            summ.append("Current test case %s" %self.current_tc.id)
            if self.current_tc.current_step:
                summ.append("Current step %s" %list((self.current_tc.current_step.to_dict(verbose=True).items())))
            else:
                summ.append("Test case hasn't started yet")
        else:
            summ.append("Testsuite not started yet")
        return summ

    def get_testcase(self,testcase_id):
        """
        :return: testcase instance or None if non existent
        """
        assert testcase_id is not None
        assert isinstance(testcase_id, str)
        try:
            return self.teds[testcase_id]
        except KeyError:
            return None


if __name__ == '__main__':

    # generate dirs
    for d in TMPDIR, DATADIR, LOGDIR:
        try:
            os.makedirs(d)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    #init logger to stnd output and log files
    initialize_logger(LOGDIR)


    def launchHttpServerLogger():
        logging.info('starting server...')
        # Server settings
        server_address = ('0.0.0.0', 8080)
        http_serv = HTTPServer(server_address, HTTPServer_RequestHandler)
        logging.info('running server...')
        http_serv.serve_forever()


    # start http server process
    http_server_p = Process(target=launchHttpServerLogger)
    http_server_p.start()


    #first lets get the AMQP params from the ENV

    try:
        AMQP_SERVER = str(os.environ['AMQP_SERVER'])
        AMQP_USER = str(os.environ['AMQP_USER'])
        AMQP_PASS = str(os.environ['AMQP_PASS'])
        AMQP_VHOST = str(os.environ['AMQP_VHOST'])
        AMQP_EXCHANGE = str(os.environ['AMQP_EXCHANGE'])


    except KeyError as e:
        logging.error(' Cannot retrieve environment variables for AMQP connection')
        # default values
        # AMQP_SERVER = "localhost"
        # AMQP_USER = "guest"
        # AMQP_PASS = "guest"
        # AMQP_VHOST = "/"
        # AMQP_EXCHANGE = "default"


    # open AMQP connection
    conn = Connection(hostname = AMQP_SERVER,
                      userid = AMQP_USER,
                      password = AMQP_PASS,
                      virtual_host = AMQP_VHOST,
                      transport_options={'confirm_publish': True})


    # start the coordinator
    # TODO point to the correct TED using session bootstrap message
    coord = Coordinator(conn,TD_COAP)

    try:
        coord.run()
    except KeyboardInterrupt as KI:
        logging.warning('Keyboard interrupt. Shutting down...')
        #shutdown http server
        http_server_p.terminate()
        #close AMQP connection
        conn.close()

    except Exception as e:
        error_msg = str(e)
        logging.error(' Critical exception found: %s' %error_msg)
        # lets push the error message into the bus

        coord.producer.publish(json.dumps({'_type':'testcoordination.error',
                                           'message': error_msg,
                                           'traceback':traceback.print_exc(),
                                           }),
                               exchange=coord.exchange,
                               routing_key='control.testcoordination.error'
                              )



