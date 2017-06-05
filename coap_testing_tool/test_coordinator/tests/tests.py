import unittest, logging, os, pika, json
from collections import OrderedDict
from coap_testing_tool import AMQP_URL
from coap_testing_tool.test_coordinator.coordinator import Coordinator, TD_COAP_CFG,TD_COAP, import_teds

class CoordinatorTestCase(unittest.TestCase):

    number_of_implemented_TCs = 24
    def setUp(self):

        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))

        # this tests import and the construction of Coordinator and test cases from yaml file
        self.coord = Coordinator(connection, TD_COAP, TD_COAP_CFG)

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
        assert len(ls) == CoordinatorTestCase.number_of_implemented_TCs
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
        for i in range(CoordinatorTestCase.number_of_implemented_TCs + 1):
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


    def test_testsuite_report(self):
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

            tc.change_state('finished')

            final_report = OrderedDict()
            final_report['verdict'] = 'test verdict'
            final_report['description'] = 'test description'
            final_report['partial_verdicts'] = 'test partial verd.'
            tc.report = final_report

            tc = c.next_testcase()
        print("TD finished!")

        print(json.dumps(c.testsuite_report()))



    def test_stepping_over_TC_config_atributes_chech_not_None(self):
        # this must not raise any errors during the iteration, control flow is done with None when iter is over!
        c = self.coord

        for conf, conf_v in c.tc_configs.items():
            print("starting with: " + conf)

            print(conf_v.id)
            print(conf_v.description)
            print(conf_v.nodes)
            print(conf_v.topology)
            print(conf_v.uri)
            print(conf_v)


if __name__ == '__main__':
    unittest.test_stepping_over_TC_config_atributes_chech_not_None()