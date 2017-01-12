# -*- coding: utf-8 -*-
#!/usr/bin/env python3

import base64
import errno
import json
import os
import traceback
import sys
import yaml
import pika
import time

from itertools import cycle
from collections import OrderedDict
from coap_testing_tool import AMQP_VHOST, AMQP_PASS,AMQP_SERVER,AMQP_USER, AMQP_EXCHANGE
from coap_testing_tool import DATADIR,TMPDIR,LOGDIR,TD_DIR, PCAP_DIR, RESULTS_DIR
from coap_testing_tool.utils.amqp_synch_call import amqp_reply, AmqpSynchronousCallClient
from coap_testing_tool.utils.exceptions import SnifferError,CoordinatorError
from coap_testing_tool.utils.logger import initialize_logger

# TODO these VARs need to come from the session orchestrator + test configuratio files
# TODO get filter from config of the TEDs
COAP_CLIENT_IUT_MODE =  'user-assisted'
COAP_SERVER_IUT_MODE = 'automated'
ANALYSIS_MODE = 'post_mortem' # either step_by_step or post_mortem
SNIFFER_FILTER_PROTO = 'udp port 5683'
# if left empty => packet_sniffer chooses the loopback
# TODO send flag to sniffer telling him to look for a tun interface instead!
SNIFFER_FILTER_IF = 'tun0'

# component identification & bus params
COMPONENT_ID = 'test_coordinator'

# set temporarily as default
# TODO get this from finterop session context!
TD_COAP = os.path.join(TD_DIR,"TD_COAP_CORE.yaml")
TD_COAP_CFG = os.path.join(TD_DIR,"TD_COAP_CFG.yaml")

# init logging to stnd output and log files
logger = initialize_logger(LOGDIR, COMPONENT_ID)


### AUX functions ###

def list_to_str(ls):
    """
    flattens a nested list up to two levels of depth

    :param ls: the list
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

### YAML parser aux classes and methods ###
def testcase_constructor(loader, node):
    instance = TestCase.__new__(TestCase)
    yield instance
    state = loader.construct_mapping(node, deep=True)
    #print("pasing test case: " + str(state))
    instance.__init__(**state)


def test_config_constructor(loader, node):
    instance = TestConfig.__new__(TestConfig)
    yield instance
    state = loader.construct_mapping(node, deep=True)
    #print("pasing test case: " + str(state))
    instance.__init__(**state)

yaml.add_constructor(u'!configuration', test_config_constructor)

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
    :param yamlfile:
    :return: list of imported testCase(s) and testConfig(s) object(s)
    """
    td_list = []
    with open(yamlfile, "r", encoding="utf-8") as stream:
        yaml_docs = yaml.load_all(stream)
        for yaml_doc in yaml_docs:
             if type(yaml_doc) is TestCase:
                 logger.debug(' Parsed test case: %s from yaml file: %s :'%(yaml_doc.id,yamlfile) )
                 td_list.append(yaml_doc)
             elif type(yaml_doc) is TestConfig:
                 logger.debug(' Parsed test case config: %s from yaml file: %s :'%(yaml_doc.id,yamlfile) )
                 td_list.append(yaml_doc)
             else:
                 logger.error('Couldnt processes import: %s from %s'%(str(yaml_doc),yamlfile))

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
    one or multiple times, either explicitly calling set_verdict() or
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
        if new_value >= self.__value:
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

class TestConfig:
    def __init__(self, configuration_id, uri, nodes, topology, description):
        self.id = configuration_id
        self.uri = uri
        self.nodes = nodes
        self.topology = topology
        self.description = description

    def to_dict(self,verbose=None):

        d = OrderedDict()
        d['configuration_id'] = self.id

        if verbose:
            d['configuration_ref'] = self.uri
            d['nodes'] = self.nodes
            d['topology'] = self.topology
            d['description'] = self.description

        return dict(d)

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
            logger.debug('Processing step init, step_id: %s, step_type: %s, ANALYSIS_MODE is %s' % (
            self.id, self.type, ANALYSIS_MODE))
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
        logger.info('Step %s state changed to: %s'%(self.id,self.state))

    def set_result(self,result,result_info):
        # Only check and verify steps can have a result
        assert self.type in ('check','verify')
        assert result in Verdict.values()
        self.partial_verdict.update(result,result_info)

class TestCase:
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
            # some sanity checks of imported steps
            try:
                assert "step_id" and "description" and "type" in s
                if s['type']=='stimuli':
                    assert "iut" in s
                self.sequence.append(Step(**s))
            except:
                logger.error("Error found while trying to parse: %s" %str(s))
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
        logger.info('Testcase %s changed state to %s'%(self.id, state))

    def check_all_steps_finished (self):
        it = iter(self.sequence)
        step = next(it)

        try:
            while True:
                # check that there's no steps in state = None or executing
                if step.state is None or step.state == 'executing':
                    logger.debug("[TESTCASE] - there are still steps to execute or under execution")
                    return False
                else:
                    step = it.__next__()
        except StopIteration:
            logger.debug("[TESTCASE] - all steps in TC are either finished or pending -> ready for analysis)")
            return True

    def generate_final_verdict(self,tat_post_mortem_analysis_report=None):
        """
        Generates the final verdict of TC and report taking into account the CHECKs and VERIFYs of the testcase
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
        logger.debug("[VERDICT GENERATION] starting the verdict generation")
        for step in self.sequence:
            # for the verdict we use the info in the checks and verify steps
            if step.type in ("check","verify"):

                logger.debug("[VERDICT GENERATION] Processing step %s" %step.id)

                if step.state == "postponed":
                    tc_report.append((step.id, None, "%s postponed" %step.type.upper(), ""))
                elif step.state == "finished":
                    tc_report.append((step.id, step.partial_verdict.get_value(), step.partial_verdict.get_message(),""))
                    # update global verdict
                    final_verdict.update(step.partial_verdict.get_value(),step.partial_verdict.get_message())
                else:
                    msg="step %s not ready for analysis"%(step.id)
                    logger.error("[VERDICT GENERATION] " + msg)
                    raise CoordinatorError(msg)

        # append at the end of the report the analysis done a posteriori (if any)
        if tat_post_mortem_analysis_report and len(tat_post_mortem_analysis_report)!=0:
            logger.warning('WTF PASEE' + str(tat_post_mortem_analysis_report))
            for item in tat_post_mortem_analysis_report:
                # TODO process the items correctly
                tc_report.append(item)
                logger.warning('WTF ' +str(item))
                final_verdict.update(item[1], item[2])
        else:
            # we cannot emit a final verdict if the report from TAT is empy (no CHECKS-> error verdict)
            logger.warning('[VERDICT GENERATION] Empty list of report passed from TAT')
            final_verdict.update('error', 'Test Analysis Tool returned an empty analysis report')

        # hack to overwrite the final verdict MESSAGE in case of pass
        if final_verdict.get_value() == 'pass':
            final_verdict.update('pass','No interoperability error was detected,')
            logger.debug("[VERDICT GENERATION] Test case executed correctly, a PASS was issued.")
        else:
            logger.debug("[VERDICT GENERATION] Test case executed correctly, but FAIL was issued as verdict.")
            logger.debug("[VERDICT GENERATION] info: %s' "%final_verdict.get_value() )

        return final_verdict.get_value(), final_verdict.get_message(), tc_report

class Coordinator:
    """
    see F-Interop API for the coordination events and services
    http://doc.f-interop.eu/#services-provided

    """

    def __init__(self, amqp_connection, ted_file, tc_configs_files):
        # first let's import the TC configurations
        imported_configs = import_teds(tc_configs_files)
        self.tc_configs = OrderedDict()
        for tc_config in imported_configs:
            self.tc_configs[tc_config.id]=tc_config

        logger.info('Imports: %s TC_CONFIG imported'%len(self.tc_configs))

        # lets import TCs and make sure there's a tc config for each one of them
        imported_teds = import_teds(ted_file)
        self.teds=OrderedDict()
        for ted in imported_teds:
            self.teds[ted.id]=ted
            if ted.configuration_id not in self.tc_configs:
                logger.error('Missing configuration:%s for test case:%s '%(ted.configuration_id,ted.id))
            assert ted.configuration_id in self.tc_configs

        logger.info('Imports: %s TC execution scripts imported' % len(self.teds))
        # test cases iterator (over the TC objects, not the keys)
        self._ted_it = cycle(self.teds.values())
        self.current_tc = None

        # AMQP queues and callbacks config
        self.connection = amqp_connection
        self.channel = self.connection.channel()

        self.services_q_name = 'services@%s' %COMPONENT_ID
        self.events_q_name = 'events@%s' %COMPONENT_ID

        result1 = self.channel.queue_declare(queue=self.services_q_name,auto_delete = True)
        result2= self.channel.queue_declare(queue=self.events_q_name,auto_delete = True)

        # self.services_q = result1.method.queue
        # self.events_q = result2.method.queue

        # # in case its not declared
        # self.channel.exchange_declare(exchange=AMQP_EXCHANGE,
        #                          type='topic',
        #                          durable=True,
        #                          )

        self.channel.queue_bind(exchange = AMQP_EXCHANGE,
                           queue = self.services_q_name,
                           routing_key = 'control.testcoordination.service')

        self.channel.queue_bind(exchange = AMQP_EXCHANGE,
                           queue = self.events_q_name,
                           routing_key = 'control.testcoordination')

        self.channel.basic_publish(
                body = json.dumps(
                        {
                            'message':'Test Coordinator is up!',
                            '_type':'testcoordination.info',
                        }
                        ),
                exchange = AMQP_EXCHANGE,
                routing_key ='control.testcoordination.info',
                properties=pika.BasicProperties(
                        content_type='application/json',
                )
            )

        self.channel.basic_consume(self.handle_service,
                              queue = self.services_q_name,
                              no_ack = False)

        self.channel.basic_consume(self.handle_control,
                              queue = self.events_q_name,
                              no_ack = False)

    def check_testsuite_finished (self):
        #cyclic as user may not have started by the first TC
        it = cycle(self.teds.values())

        # we need to check if we already did a cycle (cycle never raises StopIteration)
        iter_counts = len(self.teds)
        tc = next(it)

        while iter_counts >=0 :
            # check that there's no steps in state = None or executing
            if tc.state in (None,'executing','ready_for_analysis','analyzing'):
                logger.debug("[TESTSUITE] - there is still unfinished & non-skipped test cases")
                return False
            else: # TC state is 'skipped' or 'finished'
                tc = next(it)
            iter_counts -= 1
        if iter_counts < 0:
            logger.debug("[TESTSUITE] - Testsuite finished. No more test cases to execute.")
            return True

    def run(self):
        logger.info('start consuming..')
        self.channel.start_consuming()

    ### AUXILIARY AMQP MESSAGING FUNCTIONS ###

    def notify_tun_interfaces_start(self):
        """
        Starts tun interface in agent1, agent2 and agent TT

        Returns:

        """
        # TODO check which queues exist, get those names from somewhere and not just asumme agent1 agent2 agentTT
        d = {
            "_type": "tun.start",
            "ipv6_host": ":1",
            "ipv6_prefix": "bbbb"
        }

        logger.debug("Let's start the bootstrap the agents")

        for agent, assigned_ip in (('agent1',':1'),('agent2',':2'),('agent_TT',':3')):
            d["ipv6_host"] = assigned_ip
            self.channel.basic_publish(
                    exchange=AMQP_EXCHANGE,
                    routing_key='control.tun.toAgent.%s'%agent,
                    mandatory=True,
                    body=json.dumps(d),
                    properties=pika.BasicProperties(
                        content_type='application/json',
                    )
            )

    def notify_current_testcase(self):
        _type = 'testcoordination.testcase.next'
        r_key = 'control.testcoordination'

        # testcoordination notification
        coordinator_notif = OrderedDict()
        coordinator_notif.update({'_type':_type })
        coordinator_notif.update({'message': 'Next test case to be executed is %s' % self.current_tc.id})
        coordinator_notif.update(self.current_tc.to_dict(verbose = True))

        self.channel.basic_publish(
            body=json.dumps(coordinator_notif, ensure_ascii=False),
            routing_key=r_key,
            exchange=AMQP_EXCHANGE,
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )

    def notify_current_step_execute(self):
        _type = 'testcoordination.step.execute'
        r_key = 'control.testcoordination'

        coordinator_notif = OrderedDict()
        coordinator_notif.update({'_type':_type })
        coordinator_notif.update({'message': 'Next test step to be executed is %s' % self.current_tc.current_step.id})
        coordinator_notif.update(self.current_tc.current_step.to_dict(verbose = True))
        #coordinator_notif={**coordinator_notif,**self.current_tc.current_step.to_dict(verbose=True)}

        self.channel.basic_publish(
            body=json.dumps(coordinator_notif, ensure_ascii=False),
            routing_key=r_key,
            exchange=AMQP_EXCHANGE,
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )

    def notify_testcase_finished(self):
        _type = 'testcoordination.testcase.finished'
        r_key = 'control.testcoordination'
        # testcoordination notification
        coordinator_notif = OrderedDict()
        coordinator_notif.update({'_type': _type})
        coordinator_notif.update({'message': 'Testcase %s finished' % self.current_tc.id})
        coordinator_notif.update(self.current_tc.to_dict(verbose=True))

        self.channel.basic_publish(
            body=json.dumps(coordinator_notif, ensure_ascii=False),
            routing_key=r_key,
            exchange=AMQP_EXCHANGE,
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )

    def notify_testcase_verdict(self):
        _type = 'testcoordination.testcase.verdict'
        r_key = 'control.testcoordination'

        coordinator_notif = OrderedDict()
        coordinator_notif.update({'_type':_type })
        # lets add the report info of the TC into the answer
        coordinator_notif.update(self.current_tc.report)
        # lets add basic info about the TC
        coordinator_notif.update(self.current_tc.to_dict(verbose=True))

        self.channel.basic_publish(
            body=json.dumps(coordinator_notif, ensure_ascii=False),
            routing_key=r_key,
            exchange=AMQP_EXCHANGE,
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )

        # Overwrite final verdict file with final details
        json_file = os.path.join(
                RESULTS_DIR,
                self.current_tc.id + '_verdict.json'
        )
        with open(json_file, 'w') as f:
            json.dump(json_file, f)

    def notify_coordination_error(self, message, error_code):
        _type = 'testcoordination.error'
        r_key =  'control.testcoordination.error'

        # testcoordination.error notification
        # TODO error codes?
        coordinator_notif = OrderedDict()
        coordinator_notif.update({'_type':_type })
        coordinator_notif.update({'message': message,})
        coordinator_notif.update({'error_code' : error_code,})

        self.channel.basic_publish(
            body=json.dumps(coordinator_notif, ensure_ascii=False),
            routing_key=r_key,
            exchange=AMQP_EXCHANGE,
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )

    def notify_testsuite_finished(self):
        _type = 'testcoordination.testsuite.finished'
        r_key =  'control.testcoordination'

        coordinator_notif = OrderedDict()
        coordinator_notif.update({'_type':_type })

        self.channel.basic_publish(
            body=json.dumps(coordinator_notif, ensure_ascii=False),
            routing_key=r_key,
            exchange=AMQP_EXCHANGE,
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )

    def notify_current_configuration(self,config_id,node,message):
        _type = 'testcoordination.testcase.configuration'
        r_key =  'control.testcoordination'

        coordinator_notif = OrderedDict()
        coordinator_notif.update({'_type':_type })
        coordinator_notif.update({'configuration_id': config_id})
        coordinator_notif.update({'node': node})
        coordinator_notif.update({'message': message})

        self.channel.basic_publish(
            body=json.dumps(coordinator_notif, ensure_ascii=False),
            routing_key=r_key,
            exchange=AMQP_EXCHANGE,
            properties=pika.BasicProperties(
                content_type='application/json',
            )
        )

    def call_service_sniffer_start(self,capture_id,filter_if,filter_proto,link_id):
        _type = 'sniffing.start'
        r_key = 'control.sniffing.service'
        body = OrderedDict()
        body.update({'_type': _type})
        body.update({'capture_id': capture_id})
        body.update({'filter_if': filter_if})
        body.update({'filter_proto': filter_proto})
        body.update({'link_id':link_id})

        try:
            amqp_rpc_client = AmqpSynchronousCallClient(component_id=COMPONENT_ID)
            ret = ''
            ret = amqp_rpc_client.call(routing_key=r_key, body=body)
            logger.info("Received answer from sniffer: %s, answer: %s" % (_type,json.dumps(ret)))
            return ret['ok']
        except Exception as e:
            raise SnifferError("Sniffer API doesn't respond on %s, maybe it isn't up yet \n Exception info%s"
                           % (str(ret), str(e)))

    def call_service_sniffer_stop(self):
        _type = 'sniffing.stop'
        r_key = 'control.sniffing.service'
        body = OrderedDict()
        body.update({'_type': _type})

        try:
            amqp_rpc_client = AmqpSynchronousCallClient(component_id=COMPONENT_ID)
            ret = ''
            ret = amqp_rpc_client.call(routing_key=r_key, body=body)
            logger.info("Received answer from sniffer: %s, answer: %s" % (_type, json.dumps(ret)))
            return ret['ok']
        except Exception as e:
            raise SnifferError("Sniffer API doesn't respond on %s, maybe it isn't up yet \n Exception info%s"
                                   % (str(ret), str(e)))

    def call_service_sniffer_get_capture(self, capture_id):
        _type = 'sniffing.getcapture'
        r_key = 'control.sniffing.service'
        body = OrderedDict()
        body.update({'_type': _type})
        body.update({'capture_id': capture_id})

        try:
            amqp_rpc_client = AmqpSynchronousCallClient(component_id=COMPONENT_ID)
            ret = ''
            ret = amqp_rpc_client.call(routing_key=r_key, body=body)
            logger.info("Received answer from sniffer: %s, answer: %s" % (_type,json.dumps(ret)))
            return ret

        except Exception as e:
            raise SnifferError("Sniffer API doesn't respond on %s, maybe it isn't up yet \n Exception info%s"
                           % (str(ret), str(e)))

    def call_service_testcase_analysis(self, testcase_id, testcase_ref, file_enc, filename, value):
        _type = 'analysis.testcase.analyze'
        r_key = 'control.analysis.service'
        body = OrderedDict()
        body.update({'_type': _type})
        body.update({'testcase_id': testcase_id})
        body.update({'testcase_ref': testcase_ref})
        body.update({'file_enc': file_enc})
        body.update({'filename': filename})
        body.update({'value': value})

        try:
            amqp_rpc_client = AmqpSynchronousCallClient(component_id=COMPONENT_ID)
            ret = ''
            ret = amqp_rpc_client.call(routing_key=r_key, body=body)
            logger.info("Received answer from TAT: %s, answer: %s" % (_type, json.dumps(ret)))
            return ret

        except Exception as e:
            raise SnifferError("TAT API doesn't respond on %s, maybe it isn't up yet \n Exception info%s"
                                       % (str(ret), str(e)))


    ### API ENDPOINTS ###

    def handle_service(self, ch, method, properties, body):

        ch.basic_ack(delivery_tag=method.delivery_tag)

        # horribly long composition of methods,but  needed for keeping the order of fields of the received json object
        logger.debug('[services queue callback] service request received on the queue: %s || %s'
                     % (
                     method.routing_key, json.dumps(json.loads(body.decode('utf-8'), object_pairs_hook=OrderedDict))))

        # TODO check malformed messages first
        event = json.loads(body.decode('utf-8'),object_pairs_hook=OrderedDict)
        event_type = event['_type']

        # prepare response
        response = OrderedDict()

        if event_type == "testcoordination.testsuite.gettestcases":
            # this is a request so I answer directly on the message
            testcases = self.get_testcases_basic(verbose=True)
            response.update({'_type': event_type})
            response.update({'ok': True})
            response.update(testcases)
            amqp_reply(self.channel, properties,response)

        elif event_type == "testcoordination.testsuite.getstatus":
            status = self.states_summary()
            # this is a request so I answer directly on the message
            response.update({'_type': event_type})
            response.update({'ok': True})
            response.update({'status': status})
            amqp_reply(self.channel, properties, response)

        else:
            logger.warning('Cannot dispatch event: \nrouting_key %s \nevent_type %s' % (method.routing_key,event_type))
            return


        logger.info('Service request handled, response sent through the bus: %s'%(json.dumps(response)))


    def handle_control(self, ch, method, properties, body):

        ch.basic_ack(delivery_tag=method.delivery_tag)
        # horribly long composition of methods,but  needed for keeping the order of fields of the received json object
        logger.debug('[event queue callback] service request received on the queue: %s || %s'
                     % (
                     method.routing_key, json.dumps(json.loads(body.decode('utf-8'), object_pairs_hook=OrderedDict))))

        # TODO check malformed messages first
        event = json.loads(body.decode('utf-8'), object_pairs_hook=OrderedDict)
        event_type = event['_type']

        #prepare response
        response = OrderedDict()

        if event_type == "testcoordination.testcase.skip":

            # if no testcase_id was sent then I skip  the current one
            try:
                testcase_skip = event['testcase_id']
            except KeyError:
                testcase_skip = self.current_tc.id

            # change tc state to 'skipped'
            testcase_t = self.get_testcase(testcase_skip)
            testcase_t.change_state("skipped")

            # if skipped tc is current test case then next tc
            if self.current_tc is not None and (testcase_skip == self.current_tc.id):
                self.next_testcase()
                self.notify_current_testcase()


        elif event_type == "testcoordination.testsuite.start":
            # TODO in here maybe launch the enxt configuration of IUT
            # TODO maybe return next test case
            # TODO reboot automated IUTs

            # lets open tun interfaces
            # TODO do it before the testsuite start signal, after opened send TESTGIN TOOL ready signal (for GUI)
            self.notify_tun_interfaces_start()
            time.sleep(2)

            self.start_test_suite()

            # send general notif
            self.notify_current_testcase()

        elif event_type == "testcoordination.testcase.select":

            # assert and get testcase_id from message
            try:
                # jump to selected tc
                self.select_testcase(event['testcase_id'])

            except KeyError:
                error_msg = "Incorrect or empty testcase_id"
                # # response not ok
                # response.update({'_type': event_type})
                # response.update({'ok': False})
                # response.update({'message' : error_msg})
                # self.amqp_reply(properties, response)

                # send general notif
                self.notify_coordination_error(message=error_msg,error_code=None)

            except CoordinatorError as e:
                error_msg = e.message
                # # response not ok
                # response.update({'_type': event_type})
                # response.update({'ok': False})
                # response.update({'message': error_msg})
                # self.amqp_reply(properties, response)

                # send general notif
                self.notify_coordination_error(message=error_msg, error_code=None)


            # #response ok
            # response.update({'_type' : event_type})
            # response.update({'ok':True})
            # self.amqp_reply(properties, response)

            # send general notif
            self.notify_current_testcase()


        elif event_type == "testcoordination.testcase.start":

            if self.current_tc is None:
                error_msg = "No testcase selected"

                # # response not ok
                # response.update({'_type': event_type})
                # response.update({'ok': False})
                # response.update({'message': error_msg})
                # self.amqp_reply(properties, response)

                # notify all
                self.notify_coordination_error(message =error_msg, error_code=None)
                return

            # TODO handle configuration phase before execution!

            if self.check_testsuite_finished():
                self.notify_testsuite_finished()
            else:
                self.start_testcase()

                # send general notif
                self.notify_current_step_execute()


        elif event_type == "testcoordination.step.stimuli.executed":

            # process event only if I current step is a STIMULI
            if self.current_tc.current_step.type != 'stimuli':
                message = 'Coordination was expecting message for step type: %s , but got type: STIMULI' \
                          % (self.current_tc.current_step.type.upper())
                logger.error(message)
                self.notify_coordination_error(message, None)
                return

            self.process_stimuli_step_executed()

            # go to next step
            if self.next_step():
                self.notify_current_step_execute()
            elif not self.check_testsuite_finished():
                # im at the end of the TC:
                self.finish_testcase()
                self.notify_testcase_finished()
                self.notify_testcase_verdict()
            else:
                self.finish_testsuite()
                self.notify_testsuite_finished()

        elif event_type == "testcoordination.step.verify.response":

            # process event only if I current step is a verify
            if self.current_tc.current_step.type != 'verify':
                message = 'Coordination was expecting message for step type: %s , but got type: VERIFY' \
                          % (self.current_tc.current_step.type.upper())
                logger.error(message)
                self.notify_coordination_error(message, None)
                return

            # assert and get testcase_id from message
            try:
                verify_response = event['verify_response']
            except KeyError:
                error_msg = "Verify_response field needs to be provided"

                # send general notif
                self.notify_coordination_error(message=error_msg, error_code=None)


            self.process_verify_step_response(verify_response)

            # go to next step
            if self.next_step():
                self.notify_current_step_execute()
            elif not self.check_testsuite_finished():
                # im at the end of the TC:
                self.finish_testcase()
                self.notify_testcase_finished()
                self.notify_testcase_verdict()
            else:
                self.finish_testsuite()
                self.notify_testsuite_finished()


        elif event_type == "testcoordination.step.check.response":
            # This is call is just used when we have step_by_step analysis mode
            #assert ANALYSIS_MODE == 'step_by_step'

            # process event only if I current step is a check
            if self.current_tc.current_step.type != 'check':
                message = 'Coordination was expecting message for step type: %s , but got type: CHECK' \
                          % (self.current_tc.current_step.type.upper())
                logger.error(message)
                self.notify_coordination_error(message, None)
                return

            try:
                verdict = event['partial_verdict']
                description = event['description']
            except KeyError:
                self.notify_coordination_error(message='Malformed CHECK response', error_code=None)

            self.process_check_step_response(verdict,description)

            # go to next step
            if self.next_step():
                self.notify_current_step_execute()
            elif not self.check_testsuite_finished():
                # im at the end of the TC:
                self.finish_testcase()
                self.notify_testcase_finished()
                self.notify_testcase_verdict()
            else:
                self.finish_testsuite()
                self.notify_testsuite_finished()

        # elif event_type == "testcoordination.testcase.finish":
        #     self.finish_testcase()
        #
        #
        #     # send general notif
        #     self.notify_current_testcase()

        else:
            logger.warning('Cannot dispatch event: \nrouting_key %s \nevent_type %s' % (method.routing_key, event_type))

        logger.info('Event handled, response sent through the bus: %s'%(json.dumps(response)))



    ### TRANSITION METHODS for the Coordinator FSM ###

    def get_testcases_basic(self, verbose = None):

        resp = []
        for tc_v in self.teds.values():
            resp.append(tc_v.to_dict(verbose))
        # If no test case found
        if len(resp) == 0:
            raise CoordinatorError("No test cases found")

        return {'tc_list' : resp}

    def get_testcases_list(self):
        return list(self.teds.keys())

    #def select_testcases(self, tc_id):

    def select_testcase(self,params):
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
            logger.debug("Test case selected to be executed: %s" %self.current_tc.id)
            return self.current_tc.to_dict(verbose=True)
        else:
            logger.error( "%s not found in : %s "%(tc_id,self.teds))
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
                self.next_testcase()
            return self.current_tc
        except:
            raise

    def finish_testsuite(self):
        # TODO copy json and PCAPs to results repo
        # TODO prepare a test suite report of the tescases verdicts?
        pass

    def start_testcase(self):
        """

        :return:
        """
        # TODO add some doc!!!

        try:
            # init testcase and step and their states if they are None
            if self.current_tc is None or self.current_tc.state == 'finished':
                self.next_testcase()

            if self.current_tc.current_step is None:
                self.next_step()

            self.current_tc.change_state('executing')
        except:
            raise


        # CONFIGURATION PHASE
        config_id = self.current_tc.configuration_id
        config = self.tc_configs[config_id]

        # notify each IUT/user about the current config
        # TODO do we need a confirmation for this?
        for desc in config.description:
            message = desc['message']
            node = desc['node']
            self.notify_current_configuration(config_id,node,message)

        # start sniffing each link
        for link in config.topology:
            filter_proto = link['capture_filter']
            link_id =  link['link_id']


            sniff_params = {
                'capture_id': self.current_tc.id[:-4],
                'filter_proto': filter_proto,
                'filter_if': SNIFFER_FILTER_IF,
                'link_id' : link_id,
            }

            if self.call_service_sniffer_start(**sniff_params):
                logger.info('Sniffer succesfully started')
            else:
                logger.error('Sniffer couldnt be started')

        return self.current_tc.current_step

    def process_verify_step_response(self, verify_response):
        # some sanity checks on the states
        assert self.current_tc is not None
        assert self.current_tc.state is not None
        assert self.current_tc.current_step is not None
        assert self.current_tc.current_step.state == 'executing'
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
        logger.debug("[step_finished event] step %s, type %s -> new state : %s"
                      %(self.current_tc.current_step.id,
                        self.current_tc.current_step.type,
                        self.current_tc.current_step.state))

    def process_check_step_response(self, verdict, description):
        # some sanity checks on the states
        assert self.current_tc is not None
        assert self.current_tc.state is not None
        assert self.current_tc.current_step is not None
        assert self.current_tc.current_step.state == 'executing'

        # sanity checks on the passed params
        assert verdict is not None
        assert description is not None
        assert verdict.lower() in Verdict.__values

        self.current_tc.current_step.set_result(verdict.lower(), "CHECK step: %s" % description)
        self.current_tc.current_step.change_state('finished')

        # some info logs:
        logger.debug("[step_finished event] step %s, type %s -> new state : %s"
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
        logger.debug("[step_finished event] step %s, type %s -> new state : %s"
                      %(self.current_tc.current_step.id,
                        self.current_tc.current_step.type,
                        self.current_tc.current_step.state))

    def finish_testcase(self):
        """
        :return:
        """
        assert self.current_tc.check_all_steps_finished()
        self.current_tc.current_step = None

        # get TC params
        #tc_id = self.current_tc.id
        tc_id = self.current_tc.id[:-4]
        tc_ref = self.current_tc.uri

        self.current_tc.change_state('analyzing')
        # Finish sniffer and get PCAP
        # TODO first tell sniffer to stop!

        if ANALYSIS_MODE == 'post_mortem' :

            sniffer_response = self.call_service_sniffer_get_capture(tc_id)

            # let's try to save the file and then push it to results repo
            pcap_file_base64 = ''
            pcap_file_base64 = sniffer_response['value']
            filename = sniffer_response['filename']
            # save PCAP to file
            with open(os.path.join(PCAP_DIR, filename), "wb") as pcap_file:
                nb = pcap_file.write(base64.b64decode(pcap_file_base64))
                logger.info("Pcap correctly saved (%d Bytes) at %s" % (nb, TMPDIR))

            # Forwards PCAP to TAT API and get CHECKs info
            tat_response = self.call_service_testcase_analysis(tc_id,
                                                               tc_ref,
                                                               file_enc = "pcap_base64",
                                                               filename = tc_id+".pcap",
                                                               value = pcap_file_base64)

            logger.info("Response received from TAT: %s " % str(tat_response))

            if tat_response['ok'] == True:
                # Save the json object received
                json_file = os.path.join(
                    TMPDIR,
                    tc_id + '_analysis.json'
                )

                with open(json_file, 'w') as f:
                    json.dump(tat_response, f)

                # let's process the partial verdicts from TAT's answer
                # they come as [[str,str]] first string is partial verdict , second is description.
                partial_verd = []
                step_count = 0
                for item in tat_response['partial_verdicts']:
                    # I cannot really know which partial verdicts belongs to which step cause TAT doesnt provide me with this
                    # info, so ill make a name up(this is just for visualization purposes)
                    step_count += 1
                    p = ("CHECK_%d_post_mortem_analysis"%step_count, item[0] , item[1])
                    partial_verd.append(p)
                    logger.debug("Processing partical verdict received from TAT: %s"%str(p))

                # generates a general verdict considering other steps partial verdicts besides TAT's
                gen_verdict, gen_description, report = self.current_tc.generate_final_verdict(partial_verd)

                # save sent message in RESULTS dir
                final_report = OrderedDict()
                final_report['verdict'] = gen_verdict
                final_report['description'] = gen_description
                final_report['partial_verdicts'] = report

                # lets generate test case report
                self.current_tc.report = final_report
                # for item in overridden_response:
                #     self.current_tc.report.append(item)

                # Save the final verdict as json
                json_file = os.path.join(
                    TMPDIR,
                    tc_id + '_verdict.json'
                )
                with open(json_file, 'w') as f:
                        json.dump(final_report, f)

            else:
                logger.error('Response from TAT not ok: %s'%(tat_response))
                return

            # change tc state
            self.current_tc.change_state('finished')
            logger.info("General verdict generated: %s" %json.dumps(self.current_tc.report))

        else:
            logger.error("Error on TAT analysis reponse")
            self.notify_coordination_error("Error on TAT analysis reponse",'')
            return

        return self.current_tc.report

    def next_testcase(self):
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
        Goes to next TC if current_TC is None or finished
        :return: step or None if testcase finished

        """
        if self.current_tc is None:
            self.next_testcase()
        try:
            # if None then nothing else to execute
            if self.current_tc is None:
                return None

            self.current_tc.current_step = next(self.current_tc._step_it)

            # skip postponed steps
            while self.current_tc.current_step.state == 'postponed':
                self.current_tc.current_step = next(self.current_tc._step_it)

        except StopIteration:
            logger.info('Test case finished. No more steps to execute in testcase: %s' %self.current_tc.id)
            # return None when TC finished
            return None

        # update step state to executing
        self.current_tc.current_step.change_state('executing')

        logger.info('Next step to execute: %s' % self.current_tc.current_step.id)

        return self.current_tc.current_step

    def states_summary(self):
        summ=[]
        if self.current_tc:
            summ.append("Current test case: %s, state: %s" %(self.current_tc.id,self.current_tc.state))
            if self.current_tc.current_step:
                summ.append("Current step %s" %list((self.current_tc.current_step.to_dict(verbose=True).items())))
            else:
                summ.append("No step under execution.")
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
