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
import yaml, os, logging, json
import requests
import base64
import errno



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
LOGFILE = os.path.join( os.getcwd(), LOGDIR, 'coord.log')
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


# - - - - Test Description object model - - - - - -

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
    def __init__(self, node , mode="user_assisted"):
        # TODO get IUT mode from session config!!!
        self.node = node
        if mode:
            assert mode in ("user_assisted", "bot")
        self.mode = mode

    def execute(self,step):
        if self.mode == "user_assisted":
            # TODO implement this with the event bus
            step.change_state('executing')
            return step
        elif self.mode == "bot":
            # TODO send message to the bot queue
            pass
        else:
            raise CoordinatorError("Coudn't handle step mode")


    # TODO implement this
    def configure(self):
        pass

    def __repr__(self):
        if self.mode:
            return "%s(node=%s, mode=%s)" % (self.__class__.__name__, self.node, self.mode if self.mode else "not defined..")
        return "%s(node=%s)" % (self.__class__.__name__, self.node)

class Config:
     def __init__(self,config_id, uri, sniffers_configs, topology, sniffer_configs, description):
        pass
        #TBD

class Step():

    # TODO check step id uniqueness
    def __init__(self, step_id, type, description, iut = None):
        self.step_id = step_id
        assert type in ("stimuli","check","verify")
        # TODO sth else might need to be defined for conformance testing TBD (inject? drop packet?)..
        self.type = type
        self.description = description
        self.iut = Iut(iut)
        self.state = None
        # Check and verify steps need a partial verdict
        self.partial_verdict = Verdict()

    def __repr__(self):
        return "%s(step_id=%s, type=%s, description=%s, iut node=%s, iut mode =%s)" \
               %(self.__class__.__name__, self.step_id, self.type, self.description, self.iut.node, self.iut.mode)

    def reinit(self):
        self.change_state(None)
        if self.type in ('check','verify'):
            self.partial_verdict = Verdict()

    def to_dict(self):
        step_dict = OrderedDict()
        step_dict['_type'] = 'step'
        step_dict['step_id'] = self.step_id
        step_dict['step_type'] = self.type
        step_dict['step_info'] = self.description
        return step_dict

    def change_state(self,state):
        # postponed state used when checks are postponed for the end of the TC execution
        assert state in (None,'executing','finished','postponed')
        self.state = state
        logging.info('Step %s state changed to: %s'%(self.step_id,self.state))

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
    Analyzing -> Either TAT analysing PCAP -passive testing- or processing all partial verdicts from check steps -active testing-
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
            # TODO sanity check
            try:
                assert "step_id" and "description" and "type" in s
                self.sequence.append(Step(**s))
            except:
                logging.error("Error found while trying to parse: %s" %str(s))
                raise
        self._step_it = cycle(self.sequence)
        self.current_step = None

    def reinit(self):
        """
        - prepare test case to be re-executed
        - brings to state zero variables that might have changed during a previous execution
        :return:
        """
        self.state = None
        self.current_step = None
        self._step_it = cycle(self.sequence)

        for s in self.sequence:
            s.reinit()


    def next_step(self):
        """
        circular iterator over the steps which state is either None or 'executing'
        :return:
        """
        self.current_step = self._step_it.__next__()
        max_iters = len(self.sequence)

        # skip all finished and postponed ones
        while self.current_step.state == "finished" or self.current_step.state=='postponed':
            self.current_step = self._step_it.__next__()
            max_iters -= 1
            if max_iters < 0:
                self.current_step = None
                return None

        return self.current_step

    def __repr__(self):
        return "%s(testcase_id=%s, uri=%s, objective=%s, configuration=%s, test_sequence=%s)" % (self.__class__.__name__, self.id ,
         self.uri, self.objective, self.configuration_id,self.sequence)

    def to_dict(self,verbose=None):

        d = OrderedDict()
        d['_type'] = 'tc_basic'
        d['testcase_id'] = self.id

        if verbose:
            d['testcase_ref'] = self.uri
            d['objective'] = self.objective

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
        step = it.__next__()

        try:
            while True:
                # check that there's no steps in state = None or executing
                if step.state is None or step.state == 'executing':
                    logging.debug("[TESTCASE] - there are still steps to execute or under execution")
                    return False
                else:
                    step = it.__next__()
        except StopIteration:
            logging.debug("[TESTCASE] - all steps are either finished or pending")
            return True

    def generate_final_verdict(self,tat_analysis_report_a_posteriori=None):
        """
        Generates the final verdict and report taking into account the CHECKs and VERIFYs of the testcase
        The generated report should have the same format for both PASSIVE mode and ACTIVE mode of analysis
        :return: tuple: (final_verdict, verdict_description, tc_report) ,
                 where final_verdict in ("None", "error", "inconclusive","pass","fail")
                 where description is String type
                 where tc report is a list :[(step, step_partial_verdict, step_verdict_info, associated_frame_id (can be null))]
        """
        # TODO hanlde frame id associated to the step , used for GUI purposes
        assert self.check_all_steps_finished()

        final_verdict = Verdict()
        tc_report = []
        logging.debug("[VERDICT GENERATION] starting the verdict generation")
        for step in self.sequence:
            if step.type in ("check","verify"):

                logging.debug("[VERDICT GENERATION] Processing step %s" %step.step_id)

                if step.state == "postponed":
                    tc_report.append((step.step_id, None, "%s postponed" %step.type.upper(), ""))
                elif step.state == "finished":
                    tc_report.append((step.step_id, step.partial_verdict.get_value(), step.partial_verdict.get_message(), ""))
                    # update global verdict
                    final_verdict.update(step.partial_verdict.get_value(),step.partial_verdict.get_message())
                else:
                    msg="step %s not ready for analysis"%(step.step_id)
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
    testCoordination.selectTestCases	Message for selecting the test cases to be executed.
    api call not implemented yet, instead we preselect all and we implement a select in runtime test case (like a "jump to")
    testCoordination.selectTestCase Message for selecting next test case to be executed. Allows the user to relaunch an already executed test case.
    testCoordination.testcaseStart	Message for triggering the start of the test case. The command is given by one of the users of the session.
    testCoordination.testcaseRestart	Message for triggering the restart of a test case (TBD any of the participants MAY send this?)
    testCoordination.testcaseFinish	Message for triggering the end of a test case. This command is given by one of the users of the session.
    testCoordination.testcaseSkip	Message for skipping a test case. Coordinator passes to the next test case if there is any left.
    testCoordination.stepFinish	    Message for indicating to the coordinator that the step has already been executed.
    testCoordination.getTestCases	Message for requesting the list of test cases included in the test suite.
    testCoordination.testsuiteStart	Message for triggering start of test suite. The command is given by one of the users of the session.
    testCoordination.testsuiteAbort	Message for aborting the ongoing test session.
    """

    def __init__(self, amqp_connection, ted_file):
        # import TEDs (test extended descriptions)
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
                                   routing_key='control.testcoordination.service',
                                   durable=False)

        self.producer = self.connection.Producer(serializer='json')

        self.producer.publish(
            body = json.dumps({"_type":'testCoordinator.info','value':'Test Coordinator is up!'}),
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

        def amqp_reply(orig_message, response):

            self.producer.publish(response, exchange=self.exchange,
                             routing_key=orig_message.properties['reply_to'],
                             correlation_id=orig_message.properties['correlation_id']
                                  )
            message.ack()


        logging.debug('MESSAGE RECEIVED TO HANDLE: %s || %s' % (body, message))
        logging.debug('MESSAGE TYPE: %s || %s' % (type(body), type(message)))

        # TODO check malformed messages first
        event = json.loads(body)
        event_type = event['_type']

        #prepare reply
        reply = OrderedDict()

        if event_type == "testCoordination.getTestCases":
            testcases = self.get_test_cases_basic(verbose=True)
            reply.update({'_type' : event_type})
            reply.update({'ok': True})
            reply.update(testcases)
            amqp_reply(message,json.dumps(reply))

        if event_type == "testCoordination.testsuiteStart":
            # TODO in here maybe launch the enxt configuration of IUT
            # TODO maybe return next test case
            # TODO reboot automated IUTs
            # TODO open tun interfaces in agents
            reply['_type'] = event_type
            reply['ok'] = True
            amqp_reply(message, reply)

        elif event_type == "testCoordination.selectTestCase":
            selected_tc = self.select_test_case(event['testcase_id'])
            reply.update({'_type' : event_type})
            reply.update({'ok': True})
            # syntax introduced in Py3.5 for merging dicts
            reply = {**reply,**selected_tc}
            # TODO send notification to ALL components about this,maybe selectTestCase handles it?
            amqp_reply(message, reply)

        elif event_type == "testCoordination.startTestCase":

            # TODO handle configuration phase before execution!

            next_step = self.start_test_case()

            reply.update({'_type': event_type})
            reply.update({'ok': True})
            reply.update(next_step)
            amqp_reply(message, reply)



        elif event_type == "testCoordination.startTestSuite":
            next_tc = self.start_test_suite()
            reply['_type'] = event_type
            reply['ok'] = True
            reply.update({'testcase_next' : next_tc})
            amqp_reply(message, reply)

        elif event_type == "testCoordination.stepFinished":
            reply = self.step_finished()
            amqp_reply(message, reply)

        elif event_type == "testCoordination.processVerifyStepResponse":
            reply = self.process_verify_step_response(event['verify_response'])
            amqp_reply(message, reply)

        elif event_type == "testCoordination.finishTestCase":
            reply = self.finish_test_case()
            amqp_reply(message, reply)

        else:
            raise Exception('cannot dispatch event_type')

        logging.info('Message handled, response sent: %s'%(reply))

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
            logging.debug("Test case selected and be next executed: %s" %self.current_tc.id)
            return self.current_tc.to_dict(verbose=True)
        else:
            logging.error( "%s not found in : %s "%(tc_id,self.teds))
            raise CoordinatorError('Testcase not found')


    def start_test_suite(self):
        """
        :return: dict of the test case to start with
        """

        try:
            # resets all previously executed TC
            for tc in self.teds.values():
                tc.reinit()
            # init testcase if None
            if self.current_tc is None:
                self.next_test_case()
            return self.current_tc.to_dict(verbose=True)
        except:
            raise


    def start_test_case(self):
        """
        :return: dict of the next step to be executed
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

            return self.execute_step().to_dict()
        except:
            raise


    def process_verify_step_response(self,verify_response):
        # TODO this event should not exist, it should be merged into a finishStep
        assert verify_response is not None

        # case params corresponding to a verify step, THIS IS NOT A STEP FINISHED
        if verify_response['_type'] == "verify":
            self.current_tc.current_step.change_state('finished')
            if verify_response['response'] == True or str(verify_response['response']).lower() == 'true':
                self.current_tc.current_step.set_result("pass","VERIFY step: User informed that the information was displayed correclty on his/her IUT")
            elif verify_response['response'] == False or str(verify_response['response']).lower() == 'false':
                self.current_tc.current_step.set_result("fail","VERIFY step: User informed that the information was not displayed correclty on his/her IUT")
            else:
                self.current_tc.current_step.set_result("error",'Malformed verify response from GUI')
                raise CoordinatorError('Malformed verify response')

            return

        else:
            raise CoordinatorError('Malformed response')

    def step_finished(self):
        """
        :return: dict of the next step to be executed
        """
        def prepare_to_finish_tc(current_tc):
            current_tc.change_state('ready_for_analysis')
            return gen_final_step_executed_message(current_tc)

        # TODO stop supporting the GUI
        def gen_final_step_executed_message(current_tc):
            # GUI message
            message = OrderedDict()
            message['_type'] = 'gui_message'
            message['group'] = 'useless'
            message['dismissible'] = True
            message['content'] = 'No more steps to execute for test case %s' % current_tc.id

            information = OrderedDict()
            information['_type'] = 'information'
            information['no_more_steps'] = True

            return [message, information]


        # some info logs:
        logging.debug("[step_finished event] current step is %s state: %s" %(self.current_tc.current_step.step_id,self.current_tc.current_step.state))


        # some sanity checks on the states
        assert self.current_tc is not None
        assert self.current_tc.state is not None
        assert self.current_tc.current_step is not None
        # TODO delete this condition from next if, its redundant

        logging.debug("[step_finished event] %s ,%s" %(self.current_tc.state == 'executing',not self.current_tc.check_all_steps_finished()))
        logging.debug("[step_finished event] %s ,%s" % (self.current_tc.state, self.current_tc.check_all_steps_finished()))

        # state: TC excecuting, some steps still to be executed, and input is step stimuli finished or an empty verify (no param sent)
        if self.current_tc.state == 'executing' and not self.current_tc.check_all_steps_finished():
            logging.debug("ENTERING STATE 1")
            #  go to next step and execute
            self.current_tc.current_step.change_state('finished')
            self.next_step()
            if self.current_tc.current_step is None and self.current_tc.check_all_steps_finished():
                return prepare_to_finish_tc(self.current_tc)
            res = self.execute_step()

            # jump all non stimuli steps
            # TODO delete this when we have TATs using running in active mode
            while res is None:
                if self.next_step() is None and self.current_tc.check_all_steps_finished():
                    return prepare_to_finish_tc(self.current_tc)
                res = self.execute_step()

            # step for gui found
            return res.to_dict()

        # case : TC executing , all steps finished => change state to ready for analysis
        elif self.current_tc.state == 'executing' and self.current_tc.check_all_steps_finished():
            return prepare_to_finish_tc(self.current_tc)



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

        # Finish sniffer and get PCAP
        # TODO first tell sniffer to stop!

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

        # TODO add here if tat_mode==passive else...
        # TODO implement active analysis (step by step analysis)
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
        # TODO push to results repo
        json_save = os.path.join(
            TMPDIR,
            tc_id + '.json'
        )
        try:
            with open(json_save, 'w') as f:
                json.dump(tat_response, f)
        except:
            CoordinatorError("Couldn't write the json file")


        # let's process the partial verdicts from TAT's answer
        # they come as [[str,str]] first string is partial verdict , second is description.
        partial_verd = []
        step_count = 0
        for item in tat_response['partial_verdicts']:
            # i cannot really know which partial verdicts belongs to which step cause TAT doesnt provide me with this
            # info, so ill make a name up(this is just for viaualization purposes)
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

        ret=[]

        for item in overridden_response:
            ret.append(item)

        logging.info("General verdict generated: %s" %str(overridden_response))
        # pass to the next testcase
        tc = self.next_test_case()

        if tc:
            information = OrderedDict()
            information['_type'] = 'information'
            information['next_test_case'] = tc.id
            ret.append(information)
        else:
            information = OrderedDict()
            information['_type'] = 'information'
            information['next_test_case'] = None
            ret.append(information)

        logging.info("sending response to GUI " + json.dumps(ret))

        return ret


    def next_test_case(self):
        """
        circular iterator over the testcases returns only not yet executed ones
        :return: current test case (Tescase object) or None if nothing else left to execute
        """
        self.current_tc = self._ted_it.__next__()
        max_iters = len(self.teds)

        # get next not executed TC
        while self.current_tc.state is not None:
            self.current_tc = self._ted_it.__next__()
            max_iters -= 1
            if max_iters < 0:
                self.current_tc = None
                return None

        return self.current_tc

    def next_step(self):
        """
        same as :func:`~coordinator.TestCase.next_step`

        """
        if self.current_tc is None:
            self.next_test_case()
        resp=self.current_tc.next_step()
        if resp is None:
            logging.info('Test case finished')
        return resp

    def execute_step(self):
        """
        Notes:
            stimulis: are executed by the IUTs - either user-assisted-iut(print in GUI) or bots (agents receive the step_id and they interface with the IUTs somehow)
            checks: are executed by the TATs either in an active mode(in a synch way) or passive -at the end of the testcase-
            verify: idem as stimulis, the difference is that we receive an answer when executing these steps

        :returns: (result , next_step)
        """

        # if self.current_tc.current_step is None:
        #     self.next_step()

        assert self.current_tc.current_step is not None

        if self.current_tc.current_step.type == "stimuli":
            return self.current_tc.current_step.iut.execute(self.current_tc.current_step)

        elif self.current_tc.current_step.type == "check":
            # nothing to do in "passive mode"
            # TODO check if execution is passive or active and implement both behaviours
            self.current_tc.current_step.change_state('postponed')
            return None

        elif self.current_tc.current_step.type == "verify":
            return self.current_tc.current_step.iut.execute(self.current_tc.current_step)

    def states_summary(self):
        summ=[]
        summ.extend("Current test case %s" %self.current_tc.id,
                   "Current step %s" %self.current_tc.current_step.step_id,
                   )
        # TODO append info of already executed TCs and not yet executed ones...
        return summ


if __name__ == '__main__':

    conn = Connection('amqp://guest:guest@127.0.0.1:5672',
        transport_options={'confirm_publish': True})

    for d in TMPDIR, DATADIR, LOGDIR:
        try:
            os.makedirs(d)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    coord = Coordinator(conn,TD_COAP)

    try:
        coord.run()
    except Exception as e:
        error_msg = str(e)
        logging.error(' Critical exception found: %s' %error_msg)
        # lets push the error message into the bus
        coord.producer.publish(json.dumps({'_type':'testCoordination.error','message': error_msg}),
                               exchange=coord.exchange,
                              routing_key='control.testcoordination.error'
                              )



