# -*- coding: utf-8 -*-
# !/usr/bin/env python3

import subprocess
import logging
from event_bus_utils.rmq_handler import RabbitMQHandler, JsonFormatter
from automated_IUTs import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST, LOG_LEVEL
from automated_IUTs.automation import STIMULI_HANDLER_TOUT, AutomatedIUT

default_coap_server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

class AioCoapClient(AutomatedIUT):
    """
    Some example of usage of Aiocoap Client CLI:
    for simple GET with or without confirmable message:
        - aiocoap-client -m GET coap://[bbbb::2]:5683/test
        - aiocoap-client -m GET coap://[bbbb::2]:5683/test --non

    for GET request with optional 'accept option':
        - aiocoap-client -m GET coap://[bbbb::2]:5683/test

    for observing a resource /obs:
        - aiocoap-client -m GET --observe coap://[bbbb::2]:5683/obs

    for sending data to the server:
        - aiocoap-client -m POST --payload 'some payload'
                    coap://[[bbbb::2]]:5683/large-create
                    --content-format text/plain
        - aiocoap-client -m PUT --payload '<xml>some payload</xml>'
                    coap://[bbbb::2]:5683/create-1
                    --content-format application/xml

        The content-format option is mandatory. As Aiocoap-client do not use a
        default content--format, omiting this option will always create a
        4.00 Bad Request from the server.

    Some tests have several stimulis, those are specified with the attribute
    aux_stimuli_to_function_map.
    """
    implemented_testcases_list = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 31)]
    component_id = 'automated_iut-coap_client-aiocoap'
    node = 'coap_client'

    def __init__(self, mode_aux=None):
        logger.info('pre starting')
        super().__init__(self.node)
        logger.info('starting %s  [ %s ]' % (self.node, self.component_id))
        self.mode_aux = mode_aux
        self.iut_base_cmd_schema = 'aiocoap-client "{url}"' \
                                       .format(url=default_coap_server_base_url) + '{resource_path}'

        # mapping message's stimuli id -> function to execute this stimuli
        self.stimuli_to_function_map = {
            'TD_COAP_CORE_01_step_01': self.__stimuli_coap_core_01_10_15,
            'TD_COAP_CORE_02_step_01': self.__stimuli_coap_core_02,
            'TD_COAP_CORE_03_step_01': self.__stimuli_coap_core_03,
            'TD_COAP_CORE_04_step_01': self.__stimuli_coap_core_04_18,
            'TD_COAP_CORE_05_step_01': self.__stimuli_coap_core_05,
            'TD_COAP_CORE_06_step_01': self.__stimuli_coap_core_06,
            'TD_COAP_CORE_07_step_01': self.__stimuli_coap_core_07,
            'TD_COAP_CORE_08_step_01': self.__stimuli_coap_core_08,
            'TD_COAP_CORE_09_step_01': self.__stimuli_coap_core_09_11_16,
            'TD_COAP_CORE_10_step_01': self.__stimuli_coap_core_01_10_15,
            'TD_COAP_CORE_11_step_01': self.__stimuli_coap_core_09_11_16,
            # 'TD_COAP_CORE_12_step_01': 'TD_COAP_CORE_12',
            # 'TD_COAP_CORE_13_step_01': 'TD_COAP_CORE_13',
            'TD_COAP_CORE_14_step_01': self.__stimuli_coap_core_14,
            'TD_COAP_CORE_15_step_01': self.__stimuli_coap_core_01_10_15,
            'TD_COAP_CORE_16_step_01': self.__stimuli_coap_core_09_11_16,
            'TD_COAP_CORE_18_step_01': self.__stimuli_coap_core_04_18,
            'TD_COAP_CORE_17_step_01': self.__stimuli_coap_core_17,
            'TD_COAP_CORE_19_step_01': self.__stimuli_coap_core_19,
            'TD_COAP_CORE_20_step_01': self.__stimuli_coap_core_20_step1,
            'TD_COAP_CORE_20_step_05': self.__stimuli_coap_core_20_step5,
            'TD_COAP_CORE_21_step_01': self.__stimuli_coap_core_21_22_step1_22_step8,
            'TD_COAP_CORE_22_step_01': self.__stimuli_coap_core_21_22_step1_22_step8,
            # 'TD_COAP_CORE_22_step_04': 'TD_COAP_CORE_22',
            'TD_COAP_CORE_22_step_08': self.__stimuli_coap_core_21_22_step1_22_step8,
            # 'TD_COAP_CORE_23_step_01': 'TD_COAP_CORE_23',
            'TD_COAP_OBS_01_step_01': self.__stimuli_coap_obs_01_04_05,
            'TD_COAP_OBS_02_step_01': self.__stimuli_coap_obs_02,
            'TD_COAP_OBS_04_step_01': self.__stimuli_coap_obs_01_04_05,
            'TD_COAP_OBS_05_step_01': self.__stimuli_coap_obs_01_04_05,
            'TD_COAP_OBS_07_step_01': self.__stimuli_coap_obs_07_08_09_10_step1,
            'TD_COAP_OBS_08_step_01': self.__stimuli_coap_obs_07_08_09_10_step1,
            'TD_COAP_OBS_09_step_01': self.__stimuli_coap_obs_07_08_09_10_step1,
            'TD_COAP_OBS_10_step_01': self.__stimuli_coap_obs_07_08_09_10_step1,
            'TD_COAP_LINK_01_step_01': self.__stimuli_coap_link_01,
            'TD_COAP_LINK_02_step_01': self.__stimuli_coap_link_02,
            'TD_COAP_LINK_03_step_01': self.__stimuli_coap_link_03,
            'TD_COAP_LINK_04_step_01': self.__stimuli_coap_link_04,
            'TD_COAP_LINK_05_step_01': self.__stimuli_coap_link_05,
            'TD_COAP_LINK_06_step_01': self.__stimuli_coap_link_06,
            'TD_COAP_LINK_07_step_01': self.__stimuli_coap_link_07,
            'TD_COAP_LINK_08_step_01': self.__stimuli_coap_link_08,
            'TD_COAP_LINK_09_step_01': self.__stimuli_coap_link_09,
        }

        self.aux_stimuli_to_function_map = {
            'TD_COAP_OBS_07_step_07': self.__stimuli_coap_obs_07_step7,
            'TD_COAP_OBS_08_step_07': self.__stimuli_coap_obs_08_step7,
            'TD_COAP_OBS_09_step_07': self.__stimuli_coap_obs_09_step7,
            'TD_COAP_OBS_10_step_07': self.__stimuli_coap_obs_10_step7,
        }

        self.implemented_stimuli_list = list(self.stimuli_to_function_map.keys())

    def put(self,
            resource,
            content_format="text/plain",
            confirmable=True,
            payload="'My payload'"):
        put_cmd = self.iut_base_cmd_schema.format(resource_path=resource)
        put_cmd += ' {option} {value}'.format(option='-m', value='PUT')
        put_cmd += ' {option} {value}'.format(option='--content-format',
                                              value=content_format)
        put_cmd += ' {option} {value}'.format(option='--payload', value=payload)
        if not confirmable:
            put_cmd += ' --non'
        self.run_stimulis(cmd=put_cmd)

    def post(self,
             resource,
             content_format="text/plain",
             confirmable=True,
             payload="'My payload'"):
        post_cmd = self.iut_base_cmd_schema.format(resource_path=resource)
        post_cmd += ' {option} {value}'.format(option='-m', value='POST')
        post_cmd += ' {option} {value}'.format(option='--content-format',
                                               value=content_format)
        post_cmd += ' {option} {value}'.format(option='--payload', value=payload)
        if not confirmable:
            post_cmd += ' --non'
        self.run_stimulis(cmd=post_cmd)

    def delete(self, resource, confirmable=True):
        del_cmd = self.iut_base_cmd_schema.format(resource_path=resource)
        del_cmd += ' {option} {value}'.format(option='-m', value='DELETE')
        if not confirmable:
            del_cmd += ' --non'
        self.run_stimulis(cmd=del_cmd)

    def get(self, resource, confirmable=True, accepte_option=None):
        get_cmd = self.iut_base_cmd_schema.format(resource_path=resource)
        get_cmd += ' {option} {value}'.format(option='-m', value='GET')
        if accepte_option is not None:
            get_cmd += ' {option} {value}'.format(option='--accept',
                                                  value=accepte_option)
        if not confirmable:
            get_cmd += ' --non'
        self.run_stimulis(cmd=get_cmd)

    def observe(self, resource, confirmable=True, duration=15):
        obs_cmd = self.iut_base_cmd_schema.format(resource_path=resource)
        obs_cmd += ' --observe'
        if not confirmable:
            obs_cmd += ' --non'

        # Let our client enough time receive some
        # observations.
        self.run_stimulis(cmd=obs_cmd, timeout=duration)

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

    # CoAP BLOCK stimulis
    # TODO BLOCK_01/BLOCK_06 are not yet implemented because the CLI do not
    # allow to do early negociation. We will have to use the API to implement
    # those.

    large_payload = "<large>Lorem ipsum dolor sit amet, consectetur adipiscing\
    elit. Donec sit amet sapien ac leo bibendum suscipit at sed ipsum. Aliquam\
    in mauris nec felis dictum lobortis a et erat. Pellentesque tempus urna\
    vulputate purus faucibus ac pretium massa volutpat. Maecenas at tellus\
    neque , quis elementum ante. Morbi molestie, elit placerat rhoncus faucibus\
    , urna nunc accumsan diam, vel porta eros sem vel augue. Proin metus dolor,\
    tristique a accumsan eget, suscipit vel ante. Suspendisse feugiat, nisl non\
    viverra convallis, ante nibh congue lectus, sodales ultrices turpis massa\
    sed elit.\
    \
    Praesent posuere laoreet nulla eu accumsan. Vestibulum consequat molestie\
    erat, ut laoreet arcu mattis non. Maecenas viverra elementum mauris, vitae\
    pretium elit ultrices sit amet. Sed sit amet elit sit amet dui imperdiet\
    consequat. Donec viverra leo mollis lorem varius lacinia mollis nulla\
    posuere. Phasellus felis odio, tempor et sodales non, facilisis fermentum\
    eros. Duis dignissim massa at ante euismod vel laoreet mi tristique.\
    Nulla libero dolor, pretium vitae vulputate eget, luctus at sapien.\
    Praesent aliquam nisl ut urna pretium eu rhoncus ipsum eleifend.\
    Sed lobortis vestibulum est eu eleifend. Sed vitae luctus erat.\
    Sed vel dolor quam, tempor venenatis dolor.\
    \
    Vivamus a est a neque condimentum fermentum sed quis dui.\
    Maecenas rhoncus imperdiet tortor, vitae viverra lectus ornare vulputate.\
    Nam congue pulvinar faucibus. Vivamus id mauris at tortor porta volutpat.\
    Donec non velit a tellus placerat iaculis. Cum sociis natoque penatibus et\
    magnis dis parturient montes, nascetur ridiculus mus.\
    Suspendisse at felis ligula, vel euismod velit. Aliquam in odio urna.\
    \
    Lorem ipsum dolor sit amet, consectetur adipiscing elit.\
    Lorem ipsum dolor sit amet, consectetur adipiscing elit.\
    Nullam ac risus ipsum. Donec vel purus risus, eu molestie nisi.\
    Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere\
    cubilia Curae; Suspendisse consequat libero eu augue ornare volutpat\
    mollis sed dui. Ut sed. </large>"

    def __stimuli_coap_block_02(self):
        self.get(resource="/large")

    def __stimuli_coap_block_03(self):
        self.put(resource="/large-update", payload=self.large_payload)

    def __stimuli_coap_block_04(self):
        self.put(resource="/large-create", payload=self.large_payload)

    def __stimuli_coap_block_05(self):
        self.put(resource="/large-post", payload=self.large_payload)

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

    def _execute_stimuli(self, stimuli_step_id, addr=None):
        logger.info('got stimuli execute request: \n\tSTIMULI_ID=%s,\
                    \n\tTARGET_ADDRESS=%s' % (stimuli_step_id, addr))

        if addr:
            self.iut_base_cmd_schema = 'aiocoap-client "{url}"' \
                                           .format(url=addr) + '{resource_path}'

        if self.mode_aux:
            if stimuli_step_id not in self.aux_stimuli_to_function_map:
                logger.warning("Received request to execute unimplemented\
                               auxiliary stimulis %s", stimuli_step_id
                               )
            else:
                self.aux_stimuli_to_function_map[stimuli_step_id]()
        else:
            if stimuli_step_id not in self.stimuli_to_function_map:
                logger.warning("Received request to execute unimplemented\
                               stimulis %s", stimuli_step_id
                               )
            else:
                self.stimuli_to_function_map[stimuli_step_id]()

    def _execute_verify(self, verify_step_id):
        logger.warning('Ignoring: %s.\
                       No auto-iut mechanism for verify step implemented.'
                       % verify_step_id)

    def _execute_configuration(self, testcase_id, node):
        # no config / reset needed for implementation
        return coap_host_address

    def run_stimulis(self, cmd: str, timeout=STIMULI_HANDLER_TOUT):

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        proc.wait(timeout=timeout)

        if proc.returncode:
            logger.info('Stimulis ran sucessfully. Executed cmd is : {}'
                        .format(cmd))
        else:
            logger.info('Stimulis failed to run. Executed cmd is : {}'
                        .format(cmd))
            logger.info('Cmd output is')
            for line in proc.stdout:
                logger.info(line)


if __name__ == '__main__':

    try:
        iut = AioCoapClient()
        iut.start()
        iut.join()
    except Exception as e:
        logger.error(e)
        exit(1)
