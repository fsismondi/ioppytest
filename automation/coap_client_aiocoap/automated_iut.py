# -*- coding: utf-8 -*-
# !/usr/bin/env python3

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
    default content--format, ommiting this option will always create a
    4.00 Bad Request from the server.

******************************
NOTE about CoAP BLOCK stimuli
BLOCK_01/BLOCK_06 are not yet implemented because the CLI do not allow to do early negotiation.
We will have to use the API to implement those.
******************************

"""

import logging
from automation import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST
from automation.automated_iut import AutomatedIUT, launch_short_automated_iut_process

default_coap_server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST
BASE_CMD = ["aiocoap-client"]

logger = logging.getLogger()


# translates stimuli calls into IUT CLI calls
def get(base_url,
        resource,
        confirmable=True,
        accept_option=None,
        **kwargs):

    for k, v in kwargs.items():
        logger.warning("ignoring {}:{}".format(k, v))

    cmd = BASE_CMD.copy()
    cmd += ['{url}{resource_path}'.format(url=base_url, resource_path=resource)]
    cmd += ['-m', 'GET']
    if accept_option is not None:
        cmd += ['{option} {value}'.format(option='--accept', value=accept_option)]
    if not confirmable:
        cmd += ['--non']
    launch_short_automated_iut_process(cmd)


def put(base_url,
        resource,
        content_format="text/plain",
        confirmable=True,
        payload="'my interop test payload'",
        **kwargs):

    for k, v in kwargs.items():
        logger.warning("ignoring {}:{}".format(k, v))

    cmd = BASE_CMD.copy()
    cmd += ['{url}{resource_path}'.format(url=base_url, resource_path=resource)]
    cmd += ['-m', 'PUT', '--content-format', str(content_format), '--payload', str(payload)]
    if not confirmable:
        cmd += ['--non']
    launch_short_automated_iut_process(cmd)


def post(base_url,
         resource,
         content_format="text/plain",
         confirmable=True,
         payload="'my interop test payload'",
         **kwargs):

    for k, v in kwargs.items():
        logger.warning("ignoring {}:{}".format(k, v))

    cmd = BASE_CMD.copy()
    cmd += ['{url}{resource_path}'.format(url=base_url, resource_path=resource)]
    cmd += ['-m', 'POST', '--content-format', str(content_format), '--payload', str(payload)]
    if not confirmable:
        cmd += ['--non']
    launch_short_automated_iut_process(cmd)


def delete(base_url,
           resource,
           confirmable=True,
           **kwargs):

    for k, v in kwargs.items():
        logger.warning("ignoring {}:{}".format(k, v))

    cmd = BASE_CMD.copy()
    cmd += ['{url}{resource_path}'.format(url=base_url, resource_path=resource)]
    cmd += ['-m', 'DELETE']
    if not confirmable:
        cmd += ['--non']
    launch_short_automated_iut_process(cmd)


def observe(base_url,
            resource,
            confirmable=True,
            duration=15,
            **kwargs):

    for k, v in kwargs.items():
        logger.warning("ignoring {}:{}".format(k, v))

    cmd = BASE_CMD.copy()
    cmd += ['{url}{resource_path}'.format(url=base_url, resource_path=resource)]
    cmd += ['--observe']
    if not confirmable:
        cmd += ['--non']
    # Let our client enough time receive some observation messages.
    launch_short_automated_iut_process(cmd, timeout=duration)


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

stimuli_to_aiocoap_cli_call = {
    # CoAP CORE test cases stimuli
    "TD_COAP_CORE_01_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/test"}),
    "TD_COAP_CORE_02_step_01": (delete, {"base_url": default_coap_server_base_url, "resource": "/test"}),
    "TD_COAP_CORE_03_step_01": (
    put, {"base_url": default_coap_server_base_url, "resource": "/test", "content_format": "text/plain"}),
    "TD_COAP_CORE_04_step_01": (
    post, {"base_url": default_coap_server_base_url, "resource": "/test", "content_format": "text/plain"}),
    "TD_COAP_CORE_05_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/test", "confirmable": False}),
    "TD_COAP_CORE_06_step_01": (
    delete, {"base_url": default_coap_server_base_url, "resource": "/test", "confirmable": False}),
    "TD_COAP_CORE_07_step_01": (put, {"base_url": default_coap_server_base_url, "resource": "/test",
                                      "content_format": "text/plain", "confirmable": False}),
    "TD_COAP_CORE_08_step_01": (
    post, {"base_url": default_coap_server_base_url, "resource": "/test", "content_format": "text/plain"}),
    "TD_COAP_CORE_09_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/separate"}),
    "TD_COAP_CORE_10_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/test"}),
    "TD_COAP_CORE_11_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/separate"}),
    "TD_COAP_CORE_12_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/test", "use_token": False}),
    "TD_COAP_CORE_13_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/seg1/seg2/seg3"}),
    "TD_COAP_CORE_14_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/query?first=1&second=2&third=3"}),
    "TD_COAP_CORE_15_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/test"}),
    "TD_COAP_CORE_16_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/separate"}),
    "TD_COAP_CORE_17_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/separate", "confirmable": False}),
    "TD_COAP_CORE_18_step_01": (
    post, {"base_url": default_coap_server_base_url, "resource": "/test", "content_format": "text/plain"}),
    "TD_COAP_CORE_19_step_01": (
    post, {"base_url": default_coap_server_base_url, "resource": "/location-query?first=1&second=2&third=3"}),
    "TD_COAP_CORE_20_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/multi-format", "accept_option": "text/plain"}),
    "TD_COAP_CORE_20_step_05": (
    get, {"base_url": default_coap_server_base_url, "resource": "/multi-format", "accept_option": "application/xml"}),
    "TD_COAP_CORE_21_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/validate"}),
    "TD_COAP_CORE_22_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/validate"}),
    # "TD_COAP_CORE_22_step_04": "TD_COAP_CORE_22",
    "TD_COAP_CORE_22_step_08": (put, {"base_url": default_coap_server_base_url, "resource": "/validate"}),
    "TD_COAP_CORE_23_step_01": (put, {"base_url": default_coap_server_base_url, "resource": "/create1",
                                      "content_format": "text/plain", "use_if_none_match": True}),
    "TD_COAP_CORE_23_step_05": (put, {"base_url": default_coap_server_base_url, "resource": "/create1",
                                      "content_format": "text/plain", "use_if_none_match": True}),
    "TD_COAP_OBS_01_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs"}),
    "TD_COAP_OBS_02_step_01": (
    observe, {"base_url": default_coap_server_base_url, "resource": "/obs-non", "confirmable": False}),
    "TD_COAP_OBS_04_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs"}),
    "TD_COAP_OBS_05_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs"}),
    "TD_COAP_OBS_07_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs", "duration": 20}),
    "TD_COAP_OBS_08_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs", "duration": 20}),
    "TD_COAP_OBS_09_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs", "duration": 20}),
    "TD_COAP_OBS_10_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs", "duration": 20}),
    # CoAP BLOCK test cases stimuli
    "TD_COAP_BLOCK_01_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/large", "use_block_option": True}),
    "TD_COAP_BLOCK_02_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/large", "use_block_option": False}),
    "TD_COAP_BLOCK_03_step_01": (put, {"base_url": default_coap_server_base_url, "resource": "/large-update",
                                       "use_block_option": True, "content_format": "text/plain",
                                       "payload": large_payload}),
    "TD_COAP_BLOCK_04_step_01": (post, {"base_url": default_coap_server_base_url, "resource": "/large-create",
                                        "use_block_option": True, "content_format": "text/plain",
                                        "payload": large_payload}),
    "TD_COAP_BLOCK_05_step_01": (post, {"base_url": default_coap_server_base_url, "resource": "/large-post",
                                        "use_block_option": True, "content_format": "text/plain",
                                        "payload": large_payload}),
    "TD_COAP_BLOCK_06_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/large", "use_block_option": True, "block_size": 16}),
    # CoAP LINK test cases stimuli
    "TD_COAP_LINK_01_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core"}),
    "TD_COAP_LINK_02_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?rt=Type1"}),
    "TD_COAP_LINK_03_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?rt=*"}),
    "TD_COAP_LINK_04_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?rt=Type2"}),
    "TD_COAP_LINK_05_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?if=If*"}),
    "TD_COAP_LINK_06_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?sz=*"}),
    "TD_COAP_LINK_07_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?href=/link1"}),
    "TD_COAP_LINK_08_step_01": (
    get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?href=/link*"}),
    "TD_COAP_LINK_09_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?ct=40"}),
}


class AutomatedAiocoapClient(AutomatedIUT):
    # CoAP CoRE
    implemented_testcases_list = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 24)]
    # OBS
    implemented_testcases_list += ['TD_COAP_OBS_%02d' % tc for tc in range(1, 11)]
    # Link
    implemented_testcases_list += ['TD_COAP_LINK_%02d' % tc for tc in range(1, 10)]
    # BLOCK_01/BLOCK_06 are not yet implemented because the CLI do not allow to do early negotiation.
    implemented_testcases_list += ['TD_COAP_BLOCK_%02d' % tc for tc in range(2, 6)]

    node = 'coap_client'
    component_id = 'automated_iut-coap_client-aiocoap'
    implemented_stimuli_list = list(stimuli_to_aiocoap_cli_call.keys())
    default_coap_server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)

    def __init__(self, target_base_url=None):

        super().__init__(self.node)

        if target_base_url:
            self.base_url = target_base_url
        else:
            self.base_url = self.default_coap_server_base_url

        self.log('Started successfully %s  [ %s ]' % (self.node, self.component_id))

    # overridden methods
    def _execute_stimuli(self, stimuli_step_id, addr=None, url=None):
        """ Run stimuli using the specific CLI calls.
        You can pass addr or url, or else uses ioppytest defaults
        If you pass both addr and url, then url will be prioritized.

        - url expects formats like: url = coap://[some_ipv6_address]:port
        - addr will be used as: coap://[<addr>]:defautl_port

        """

        self.log('Got stimuli execute request: \n\tSTIMULI_ID=%s,\n\tTARGET_ADDRESS=%s' % (stimuli_step_id, addr))

        # redefines default
        if url:
            self.base_url = url
        elif addr:
            self.base_url = 'coap://[%s]:%s' % (addr, COAP_SERVER_PORT)  # fixMe I'm assuming it's IPv6!

        try:
            func, args = stimuli_to_aiocoap_cli_call[stimuli_step_id]
        except KeyError:
            raise Exception("Received request to execute unimplemented stimuli %s", stimuli_step_id)

        args['base_url'] = self.base_url  # update with target url received from event
        func(**args)  # spawn stimuli process

    def _execute_verify(self, verify_step_id):
        self.log('Ignoring: %s. No auto-iut mechanism for verify step implemented.' % verify_step_id)

    def _execute_configuration(self, testcase_id, node):
        # no config / reset needed for implementation
        return coap_host_address


if __name__ == '__main__':
    try:
        iut = AutomatedAiocoapClient()
        iut.start()
        iut.join()
    except Exception as e:
        logger.error(e)
        exit(1)
