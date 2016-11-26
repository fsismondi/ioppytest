import unittest, logging, os
from kombu import Connection
from coap_testing_tool.test_coordinator.coordinator import Coordinator,import_teds
from coap_testing_tool.utils.exceptions import CoordinatorError, TatError, SnifferError
from coap_testing_tool import *

TD_COAP = os.path.join(TD_DIR,'TD_COAP_CORE.yaml')

class CoordinatorTestCase(unittest.TestCase):

    def setUp(self):

        #print( str(os.environ['PYTHON_PATH']))
        logging.basicConfig(level=logging.DEBUG)

        conn = Connection(hostname=AMQP_SERVER,
                          userid=AMQP_USER,
                          password=AMQP_PASS,
                          virtual_host=AMQP_VHOST,
                          transport_options={'confirm_publish': True})

        # it docs its a raw import

        # this tests import and the construction of Coordinator and test cases from yaml file
        self.coord = Coordinator(conn,TD_COAP)

    def test_parse_yaml(self):
        logging.debug("raw parse : ")
        it_docs = import_teds(TD_COAP)
        for d in self.coord.teds:
            logging.debug(d)
        logging.debug( it_docs)
        for item in it_docs:
            print(str(type(item)))
            logging.debug(str(type(item)))
            logging.debug(str(item))

    def test_get_test_cases_as_list(self):
        logging.debug("LIST OF TEST CASES: ")
        ls = self.coord.get_test_cases_list()
        assert len(ls)==3
        logging.debug(ls)

    def test_select_test_case(self):
        self.coord.select_test_case('TD_COAP_CORE_02_v01')
        assert self.coord.current_tc.id == 'TD_COAP_CORE_02_v01'


    def test_check_all_steps_finished(self):
        # this must not raise any errors during the iteration, control flow is done with None when iter is over!
        c = self.coord
        tc = c.next_test_case()
        assert tc is not None
        logging.debug("starting check_finished() method test")
        for p in tc.sequence:
            assert tc.check_all_steps_finished() is False
            p.change_state('postponed')
            logging.warning('step state: '+ str(p.state))
        assert tc.check_all_steps_finished() is True
        logging.debug("TD finished!")

    def test_stepping_over_the_test_cases(self):
        c = self.coord
        for i in range(4):
            tc = c.next_test_case()
            if tc:
                tc.change_state('skipped')
            logging.info("iter over TCs: \n" + str(tc))
        assert tc == None


    def test_stepping_over_the_steps_and_the_TCs(self):
        # this must not raise any errors during the iteration, control flow is done with None when iter is over!
        c = self.coord
        tc = c.next_test_case()
        assert tc is not None

        logging.debug("starting iteration over all steps in the TD")
        logging.debug("starting with: " + tc.id)

        while tc is not None:
            logging.debug("running TC: "+ str(tc.id))
            s = c.next_step()

            while s is not None:
                logging.debug("\t passing: " + s.id)
                s.change_state('postponed')
                s = c.next_step()

            tc.change_state('skipped')
            tc = c.next_test_case()
        logging.debug("TD finished!")



            # def test_step_execution(self):
    #     c = self.coord
    #     tc = c.next_test_case()
    #     logging.debug("starting execution of steps in the TD")
    #     logging.debug("starting with: " + tc.id)
    #     while tc is not None:
    #         logging.debug("\t running TC: "+ str(tc.id))
    #         res , s_next = c.execute_step()
    #         logging.debug("\t return: %s next step %s" %(res , s_next))
    #         s = s_next
    #         while s is not None:
    #             logging.debug("\t \t  step executed: %s , type: %s" %(s.id,s.type))
    #             res, s_next = c.execute_step()
    #             logging.debug("\t \t  step executed RESULT: : %s " % (res))
    #             s = s_next
    #
    #
    #         tc = c.next_test_case()
    #     logging.debug("TD EXECUTION finished!")


if __name__ == '__main__':
    unittest.main()