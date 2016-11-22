import unittest, logging
from coap_testing_tool.test_coordinator.coordinator import Coordinator,import_teds, CoordinatorError, TatError, SnifferError

class CoordinatorTestCase(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)
        self.TD = 'TD_COAP_CORE.yaml'
        # it docs its a raw import

        # this tests import and the construction of Coordinator and test cases from yaml file
        self.coord = Coordinator(self.TD)

    def test_parse_yaml(self):
        logging.debug("raw parse : ")
        it_docs = import_teds(self.TD)
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
        assert self.coord.current_test_case.testcase_id == 'TD_COAP_CORE_02_v01'


    def test_check_finished(self):
        # this must not raise any errors during the iteration, control flow is done with None when iter is over!
        c = self.coord
        tc = c.next_test_case()
        assert tc is not None
        logging.debug("starting check_finished() method test")
        for p in tc.sequence:
            assert tc.check_finished() is False
            p.change_state('postponed')
            logging.warning('step state: '+ str(p._state))
        assert tc.check_finished() is True
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
        logging.debug("starting with: " + tc.testcase_id)

        while tc is not None:
            logging.debug("running TC: "+ str(tc.testcase_id))
            s = c.next_step()

            while s is not None:
                logging.debug("\t passing: " + s.step_id)
                s.change_state('postponed')
                s = c.next_step()

            tc.change_state('skipped')
            tc = c.next_test_case()
        logging.debug("TD finished!")



            # def test_step_execution(self):
    #     c = self.coord
    #     tc = c.next_test_case()
    #     logging.debug("starting execution of steps in the TD")
    #     logging.debug("starting with: " + tc.testcase_id)
    #     while tc is not None:
    #         logging.debug("\t running TC: "+ str(tc.testcase_id))
    #         res , s_next = c.execute_step()
    #         logging.debug("\t return: %s next step %s" %(res , s_next))
    #         s = s_next
    #         while s is not None:
    #             logging.debug("\t \t  step executed: %s , type: %s" %(s.step_id,s.type))
    #             res, s_next = c.execute_step()
    #             logging.debug("\t \t  step executed RESULT: : %s " % (res))
    #             s = s_next
    #
    #
    #         tc = c.next_test_case()
    #     logging.debug("TD EXECUTION finished!")


if __name__ == '__main__':
    unittest.main()