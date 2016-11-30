import unittest, logging, os
from coap_testing_tool.test_coordinator.coordinator import *
from coap_testing_tool import LOGDIR,TD_DIR

TD_COAP = os.path.join(TD_DIR,'TD_COAP_CORE.yaml')

class CoordinatorTestCase(unittest.TestCase):

    def setUp(self):

        #print( str(os.environ['PYTHON_PATH']))
        credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASS)
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=AMQP_SERVER,
            virtual_host=AMQP_VHOST,
            credentials = credentials))

        # it docs its a raw import

        # this tests import and the construction of Coordinator and test cases from yaml file
        self.coord = Coordinator(connection,TD_COAP)

    def test_parse_yaml(self):
        print("raw parse : ")
        it_docs = import_teds(TD_COAP)
        for d in self.coord.teds:
            print(d)
        print( it_docs)
        for item in it_docs:
            print(str(type(item)))
            print(str(type(item)))
            print(str(item))

    def test_get_testcases_as_list(self):
        print("LIST OF TEST CASES: ")
        ls = self.coord.get_testcases_list()
        assert len(ls)==3
        print(ls)

    def test_select_testcase(self):
        self.coord.select_testcase('TD_COAP_CORE_02_v01')
        assert self.coord.current_tc.id == 'TD_COAP_CORE_02_v01'


    def test_check_all_steps_finished(self):
        # this must not raise any errors during the iteration, control flow is done with None when iter is over!
        c = self.coord
        tc = c.next_testcase()
        assert tc is not None
        print("starting check_finished() method test")
        for p in tc.sequence:
            assert tc.check_all_steps_finished() is False
            p.change_state('postponed')
            print('step state: '+ str(p.state))
        assert tc.check_all_steps_finished() is True
        print("TD finished!")

    def test_stepping_over_the_testcases(self):
        c = self.coord
        for i in range(4):
            tc = c.next_testcase()
            if tc:
                tc.change_state('skipped')
            print("iter over TCs: \n" + str(tc))
        assert tc == None


    def test_stepping_over_the_steps_and_the_TCs(self):
        # this must not raise any errors during the iteration, control flow is done with None when iter is over!
        c = self.coord
        tc = c.next_testcase()
        assert tc is not None

        print("starting iteration over all steps in the TD")
        print("starting with: " + tc.id)

        while tc is not None:
            print("running TC: "+ str(tc.id))
            s = c.next_step()

            while s is not None:
                print("\t passing: " + s.id)
                s.change_state('postponed')
                s = c.next_step()

            tc.change_state('skipped')
            tc = c.next_testcase()
        print("TD finished!")



            # def test_step_execution(self):
    #     c = self.coord
    #     tc = c.next_testcase()
    #     print("starting execution of steps in the TD")
    #     print("starting with: " + tc.id)
    #     while tc is not None:
    #         print("\t running TC: "+ str(tc.id))
    #         res , s_next = c.execute_step()
    #         print("\t return: %s next step %s" %(res , s_next))
    #         s = s_next
    #         while s is not None:
    #             print("\t \t  step executed: %s , type: %s" %(s.id,s.type))
    #             res, s_next = c.execute_step()
    #             print("\t \t  step executed RESULT: : %s " % (res))
    #             s = s_next
    #
    #
    #         tc = c.next_testcase()
    #     print("TD EXECUTION finished!")


if __name__ == '__main__':
    unittest.main()