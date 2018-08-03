# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import os
import subprocess
import binascii
import logging
from automated_IUTs import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST, LOG_LEVEL
from automated_IUTs.automation import STIMULI_HANDLER_TOUT, AutomatedIUT

default_coap_server_base_url = 'coap://[%s]:%s' %(COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST

class LibcoapClient(AutomatedIUT):
    """
    Some example of usage of Libcoap Client CLI:

    It is important to use the -T option to specify the token, because without
    it, the CLI will use empty token, this will pose issues for conversation
    preprocessing. This IUT use __get_random_token() method to obtains a new
    token for every new request.

    For simple GET with or without confirmable message:
        coap-client coap://[127.0.0.1]:5683/test -m GET -T ABCD1234
        coap-client coap://[127.0.0.1]:5683/test -m GET -N -T ABCD1234

    for GET request with one or several optional 'accept option(s)':
        coap-client coap://[127.0.0.1]:5683/test
                    -m GET -A text/plain -T ABCD1234
        coap-client coap://[127.0.0.1]:5683/test
                    -m GET -A text/plain -A application/xml -T ABCD1234


    for observing a resource /obs, we have to use the -s option followed by
    the ammount of second we want to observe the specified resource,
    e.g for 15 secondes :
        - coap-client -s 15 "coap://[bbbb::2]:5683/obs" -T ABCD1234

    At the end of this specified timeout, the IUT will deregister properly
    using a GET request with observe option set to one.

    for sending data to the server:
        - coap-client -m POST -e 'some payload'
                    "coap://[bbbb::2]:5683/large-create"
                    -t text/plain -T ABCD1234
        - coap-client -m PUT -e '<xml>some payload</xml>'
                    "coap://[bbbb::2]:5683/create-1"
                    -t application/xml -T ABCD1234
        - coap-client -m PUT -f /path/to/file
                    "coap://[bbbb::2]:5683/create-1"
                    -t application/xml -T ABCD1234

        In CoAP protocol, the content-format option is mandatory with POST/PUT.
        If the -t option for content_format is unspecified, libcoap will
        automatically use application/octet-stream by default.

    For BLOCKWISE transfert, we use the -b switch that specify the starting
    block number and the desired block size with the following syntax:
    -b 3,256. In this example, we start retrieving the 3rd block with a
    blocksize of 256. Note that using a starting block number different than 0
    is only allowed for GET request.

    For POST/BLOCK request, the blocksize is mandatory for large file,
    the CLI will not choose a default value.

    For GET request, the blocksize is only to be specified for early negociation
    (client side). To use late negociation (server side), we do not need
    to use any option and just do a basic GET request.
    Example of usage:
        - coap-client -m GET coap://[bbbb::2]:5683/large -b 0,256
        - coap-client -m PUT -f /path/to/file
                    coap://[bbbb::2]:5683/large-update
                    -t application/xml -T ABCD1234 -b 0,128
        - coap-client -m POST -f /path/to/file
                    coap://[bbbb::2]:5683/large-post
                    -t application/xml -T ABCD1234 -b 0,256

    Some tests have several stimulis, those are specified with the attribute
    aux_stimuli_to_function_map.
    """
    implemented_testcases_list = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 31)]
    component_id = 'automated_iut-coap_client-libcoap'
    node = 'coap_client'
    large_payload_test_file = 'automated_IUTs/coap_client_libcoap/\
                              file/etsi_iot_01_largedata.txt'
    default_coap_server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)

    def __init__(self, mode_aux=None):
        super().__init__(self.node)
        self.log('starting %s  [ %s ]' % (self.node, self.component_id))
        self.mode_aux = mode_aux
        self.base_url = self.default_coap_server_base_url
        self.base_cmd = ["coap-client"]

    # mapping message's stimuli id -> function to execute this stimuli
    self.stimuli_to_function_map = {
        'TD_COAP_CORE_01_step_01': __stimuli_coap_core_01_10_15,
        'TD_COAP_CORE_02_step_01': __stimuli_coap_core_02,
        'TD_COAP_CORE_03_step_01': __stimuli_coap_core_03,
        'TD_COAP_CORE_04_step_01': __stimuli_coap_core_04_18,
        'TD_COAP_CORE_05_step_01': __stimuli_coap_core_05,
        'TD_COAP_CORE_06_step_01': __stimuli_coap_core_06,
        'TD_COAP_CORE_07_step_01': __stimuli_coap_core_07,
        'TD_COAP_CORE_08_step_01': __stimuli_coap_core_08,
        'TD_COAP_CORE_09_step_01': __stimuli_coap_core_09_11_16,
        'TD_COAP_CORE_10_step_01': __stimuli_coap_core_01_10_15,
        'TD_COAP_CORE_11_step_01': __stimuli_coap_core_09_11_16,
        'TD_COAP_CORE_12_step_01': __stimuli_coap_core_12,
        'TD_COAP_CORE_13_step_01': __stimuli_coap_core_13,
        'TD_COAP_CORE_14_step_01': __stimuli_coap_core_14,
        'TD_COAP_CORE_15_step_01': __stimuli_coap_core_01_10_15,
        'TD_COAP_CORE_16_step_01': __stimuli_coap_core_09_11_16,
        'TD_COAP_CORE_18_step_01': __stimuli_coap_core_04_18,
        'TD_COAP_CORE_17_step_01': __stimuli_coap_core_17,
        'TD_COAP_CORE_19_step_01': __stimuli_coap_core_19,
        'TD_COAP_CORE_20_step_01': __stimuli_coap_core_20_step1,
        'TD_COAP_CORE_20_step_05': __stimuli_coap_core_20_step5,
        'TD_COAP_CORE_21_step_01': __stimuli_coap_core_21_22_step1_22_step8,
        'TD_COAP_CORE_22_step_01': __stimuli_coap_core_21_22_step1_22_step8,
        # 'TD_COAP_CORE_22_step_04': 'TD_COAP_CORE_22',
        'TD_COAP_CORE_22_step_08': __stimuli_coap_core_21_22_step1_22_step8,
        'TD_COAP_CORE_23_step_01': __stimuli_coap_core_23,
        'TD_COAP_CORE_23_step_05': __stimuli_coap_core_23,
        'TD_COAP_OBS_01_step_01': __stimuli_coap_obs_01_04_05,
        'TD_COAP_OBS_02_step_01': __stimuli_coap_obs_02,
        'TD_COAP_OBS_04_step_01': __stimuli_coap_obs_01_04_05,
        'TD_COAP_OBS_05_step_01': __stimuli_coap_obs_01_04_05,
        'TD_COAP_OBS_07_step_01': __stimuli_coap_obs_07_08_09_10_step1,
        'TD_COAP_OBS_08_step_01': __stimuli_coap_obs_07_08_09_10_step1,
        'TD_COAP_OBS_09_step_01': __stimuli_coap_obs_07_08_09_10_step1,
        'TD_COAP_OBS_10_step_01': __stimuli_coap_obs_07_08_09_10_step1,
        'TD_COAP_BLOCK_01_step_01': __stimuli_coap_block_01,
        'TD_COAP_BLOCK_02_step_01': __stimuli_coap_block_02,
        'TD_COAP_BLOCK_03_step_01': __stimuli_coap_block_03,
        'TD_COAP_BLOCK_04_step_01': __stimuli_coap_block_04,
        'TD_COAP_BLOCK_05_step_01': __stimuli_coap_block_05,
        'TD_COAP_BLOCK_06_step_01': __stimuli_coap_block_06,
        'TD_COAP_LINK_01_step_01': __stimuli_coap_link_01,
        'TD_COAP_LINK_02_step_01': __stimuli_coap_link_02,
        'TD_COAP_LINK_03_step_01': __stimuli_coap_link_03,
        'TD_COAP_LINK_04_step_01': __stimuli_coap_link_04,
        'TD_COAP_LINK_05_step_01': __stimuli_coap_link_05,
        'TD_COAP_LINK_06_step_01': __stimuli_coap_link_06,
        'TD_COAP_LINK_07_step_01': __stimuli_coap_link_07,
        'TD_COAP_LINK_08_step_01': __stimuli_coap_link_08,
        'TD_COAP_LINK_09_step_01': __stimuli_coap_link_09,
    }

    self.aux_stimuli_to_function_map = {
        'TD_COAP_OBS_07_step_07': __stimuli_coap_obs_07_step7,
        'TD_COAP_OBS_08_step_07': __stimuli_coap_obs_08_step7,
        'TD_COAP_OBS_09_step_07': __stimuli_coap_obs_09_step7,
        'TD_COAP_OBS_10_step_07': __stimuli_coap_obs_10_step7,
    }

    self.implemented_stimuli_list = list(stimuli_to_function_map.keys())

    def _run_cmd_as_subprocess(self, cmd: list, timeout=STIMULI_HANDLER_TOUT):
        assert type(cmd) is list

        try:
            o = subprocess.check_output(cmd,stderr=subprocess.STDOUT,shell=False,timeout=timeout,universal_newlines=True)
        except subprocess.CalledProcessError as p_err:
            self.log('Stimuli failed (ret code: {}). Executed cmd is : {}'.format(p_err.returncode, cmd))
            self.log('Error: {}'.format(p_err))
            return
        except Exception as err:
            self.log('Error found: {}, trying to run: {}, got as output {}'.format(err, cmd, o))
            return

        self.log('Stimuli ran successfully (ret code: {}). Executed cmd is : {}'.format(str(o), cmd))

    def get(self,
            resource,
            confirmable=True,
            use_token=True,
            accepte_option=None,
            use_block_option=False):
        cmd = self.base_cmd.copy()
        cmd += ['{url}{resource_path}'.format(url=self.base_url, resource_path=resource)]
        cmd += ['-m', 'GET']
        if accepte_option is not None:
            cmd += ['{option} {value}'.format(option='-A', value=accepte_option)]
        if not confirmable:
            cmd += ['-N']
        if use_token:
            tkn = self.__get_random_token()
            cmd += ['{option} {value}'.format(option='-T', value=tkn)]
        if use_block_option:
            cmd += ['{option} {value}'.format(option='-b', value="0,64")]
        self._run_cmd_as_subprocess(cmd=cmd)

    def put(self,
            resource,
            content_format="text/plain",
            confirmable=True,
            use_token=True,
            use_if_none_match=False,
            use_block_option=False,
            desired_block_size=64,
            payload="'my interop test payload'",
            filepath_payload=None):
        """
        Note: if a file to send is specified with filepath_payload argument,
        the payload argument is ignored.
        """
        cmd = self.base_cmd.copy()
        cmd += ['{url}{resource_path}'.format(url=self.base_url, resource_path=resource)]
        cmd += ['-m', 'PUT', '-t', str(content_format)]
        if filepath_payload:
            cmd += ['-f', str(filepath_payload)]
        else:
            cmd += ['-e', str(payload)]
        if not confirmable:
            cmd += ['-N']
        if use_token:
            tkn = self.__get_random_token()
            cmd += ['-T', str(tkn)]
        if use_if_none_match:
            cmd += ['-O', str(5)]
        if use_block_option:
            block_option_val = '{start_number} {desired_block_size}'\
                               .format(start_number=0,
                                       desired_block_size=desired_block_size)
            cmd =['-b', str(block_option_val)]
        self._run_cmd_as_subprocess(cmd=cmd)

    def post(self,
             resource,
             content_format="text/plain",
             confirmable=True,
             use_token=True,
             use_block_option=False,
             desired_block_size=64,
             payload="'my interop test payload'",
             filepath_payload=None):
            cmd = self.base_cmd.copy()
            cmd += ['{url}{resource_path}'.format(url=self.base_url, resource_path=resource)]
            cmd += ['-m', 'POST', '-t', str(content_format)]
        if filepath_payload:
            cmd += ' {option} {value}'.format(option='-f', value=filepath_payload)
        else:
            cmd += ' {option} {value}'.format(option='-e', value=payload)
        if not confirmable:
            cmd += ['-N']
        if use_token:
            tkn = self.__get_random_token()
            cmd += ['-T', str(tkn)]
        if use_block_option:
            block_option_val = '{start_number} {desired_block_size}'\
                               .format(start_number=0,
                                       desired_block_size=desired_block_size)
            cmd =['-b', str(block_option_val)]
        self._run_cmd_as_subprocess(cmd=cmd)

    def delete(self, resource, confirmable=True, use_token=True):
        cmd = self.base_cmd.copy()
        cmd += ['{url}{resource_path}'.format(url=self.base_url, resource_path=resource)]
        cmd += ['-m', 'DELETE', '-t', str(content_format)]
        if not confirmable:
            cmd += ['-N']
        if use_token:
            tkn = self.__get_random_token()
            cmd += ['-T', str(tkn)]
        self._run_cmd_as_subprocess(cmd=cmd)

    def observe(self, resource, confirmable=True, use_token=True, duration=15):
        cmd = self.base_cmd.copy()
        cmd += ['{url}{resource_path}'.format(url=self.base_url, resource_path=resource)]

        cmd += ['-s', str(duration)]
        if not confirmable:
            cmd += ['-N']
        if use_token:
            tkn = self.__get_random_token()
            cmd += ['-T', str(tkn)]
        self._run_cmd_as_subprocess(cmd=cmd, timeout=duration)

    def __get_random_token(self):
        return binascii.hexlify(os.urandom(8))

    # Coap Core stimulus

    def __stimuli_coap_core_01_10_15(self):
        self.get(resource="/test")

    def __stimuli_coap_core_02(self):
        self.delete(resource="/test")

    def __stimuli_coap_core_03(self):
        self.put(resource="/test", content_format="text/plain")

    def __stimuli_coap_core_04_18(self):
        self.post(resource="/test", content_format="text/plain")

    def __stimuli_coap_core_05(self):
        self.get(resource="/test", confirmable=False)

    def __stimuli_coap_core_06(self):
        self.delete(resource="/test", confirmable=False)

    def __stimuli_coap_core_07(self):
        self.put(resource="/test", content_format="text/plain", confirmable=False)

    def __stimuli_coap_core_08(self):
        self.post(resource="/test", content_format="text/plain", confirmable=False)

    def __stimuli_coap_core_09_11_16(self):
        self.get(resource="/separate")

    def __stimuli_coap_core_12(self):
        self.get(resource="/test", use_token=False)

    def __stimuli_coap_core_13(self):
        self.get(resource="/seg1/seg2/seg3")

    def __stimuli_coap_core_14(self):
        self.get(resource="/query?first=1&second=2&third=3")

    def __stimuli_coap_core_17(self):
        self.get(resource="/separate", confirmable=False)

    def __stimuli_coap_core_19(self):
        self.post(resource="/location-query?first=1&second=2&third=3")

    def __stimuli_coap_core_20_step1(self):
        self.get(resource="/multi-format", accepte_option="text/plain")

    def __stimuli_coap_core_20_step5(self):
        self.get(resource="/multi-format", accepte_option="application/xml")

    def __stimuli_coap_core_21_22_step1_22_step8(self):
        self.get(resource="/validate")

    def __stimuli_coap_core_23(self):
        self.put(resource="/create1",
                 content_format="text/plain",
                 use_if_none_match=True)

    # Coap Observe stimulus

    def __stimuli_coap_obs_01_04_05(self):
        self.observe(resource="/obs")

    def __stimuli_coap_obs_02(self):
        self.observe(resource="/obs-non", confirmable=False)

    def __stimuli_coap_obs_07_08_09_10_step1(self):
        self.observe(resource="/obs", duration=20)

    # Coap OBS auxiliary stimulus

    def __stimuli_coap_obs_07_step7(self):
        self.delete(resource="/obs")

    # Update the /obs resource of with new payload having a different Content-format
    # Warning : We do assume that the former content format was NOT already application/xml
    # If not the test result will be inconclusive.
    def __stimuli_coap_obs_08_step7(self):
        self.put(resource="/obs",
                 content_format="application/xml",
                 confirmable=True,
                 payload="'My new payload with a new content-format.'")

    # Update the /obs resource of with new payload having the same Content-format
    # Warning : We do assume that the current content format was already text/plain
    # If not the test result will be inconclusive.
    def __stimuli_coap_obs_09_step7(self):
        self.put(resource="/obs",
                 content_format="text/plain",
                 confirmable=True,
                 payload="'My new payload with the same content-format.'")

    def __stimuli_coap_obs_10_step7(self):
        self.get(resource="/obs", confirmable=True)

    # CoAP BLOCK stimulis.

    def __stimuli_coap_block_01(self):
        self.get(resource="/large", use_block_option=True)

    def __stimuli_coap_block_02(self):
        self.get(resource="/large", use_block_option=False)

    def __stimuli_coap_block_03(self):
        self.put(resource="/large-update",
                 use_block_option=True,
                 content_format="text/plain",
                 filepath_payload=self.large_payload_test_file)

    def __stimuli_coap_block_04(self):
        self.post(resource="/large-create",
                  use_block_option=True,
                  content_format="text/plain",
                  filepath_payload=self.large_payload_test_file)

    def __stimuli_coap_block_05(self):
        self.post(resource="/large-post",
                  use_block_option=True,
                  content_format="text/plain",
                  filepath_payload=self.large_payload_test_file)

    def __stimuli_coap_block_06(self):
        self.get(resource="/large",
                 use_block_option=True,
                 desired_block_size=16)

    # CoAP LINK stimulis.

    def __stimuli_coap_link_01(self):
        self.get(resource="/.well-known/core")

    def __stimuli_coap_link_02(self):
        self.get(resource="/.well-known/core?rt=Type1")

    def __stimuli_coap_link_03(self):
        self.get(resource="/.well-known/core?rt=*")

    def __stimuli_coap_link_04(self):
        self.get(resource="/.well-known/core?rt=Type2")

    def __stimuli_coap_link_05(self):
        self.get(resource="/.well-known/core?if=If*")

    def __stimuli_coap_link_06(self):
        self.get(resource="/.well-known/core?sz=*")

    def __stimuli_coap_link_07(self):
        self.get(resource="/.well-known/core?href=/link1")

    def __stimuli_coap_link_08(self):
        self.get(resource="/.well-known/core?href=/link*")

    def __stimuli_coap_link_09(self):
        self.get(resource="/.well-known/core?ct=40")

    # overridden methods

    def _execute_stimuli(self, stimuli_step_id, addr=None):
        self.log('Got stimuli execute request: \n\tSTIMULI_ID=%s,\n\tTARGET_ADDRESS=%s' % (stimuli_step_id, addr))

        # redefines default
        if addr:
            self.base_url = 'coap://[%s]:%s' % (addr, COAP_SERVER_PORT)  # rewrites default

        if self.mode_aux:
            if stimuli_step_id not in self.aux_stimuli_to_function_map:
                self.log("Received request to execute unimplemented auxiliary stimuli %s", stimuli_step_id)
            else:
                self.aux_stimuli_to_function_map[stimuli_step_id]()
        else:
            if stimuli_step_id not in self.stimuli_to_function_map:
                self.log("Received request to execute unimplemented stimuli %s", stimuli_step_id)
            else:
                self.stimuli_to_function_map[stimuli_step_id]()

    def _execute_verify(self, verify_step_id):
        logger.warning('Ignoring: %s.\
                       No auto-iut mechanism for verify step implemented.'
                       % verify_step_id)

    def _execute_configuration(self, testcase_id, node):
        # no config / reset needed for implementation
        return coap_host_address


if __name__ == '__main__':

    try:
        iut = LibcoapClient()
        iut.start()
        iut.join()
    except Exception as e:
        logging.error(e)
        exit(1)
