# -*- coding: utf-8 -*-
# !/usr/bin/env python3

"""
Some example of usage of Libcoap Client CLI:

It is important to use the -T option to specify the token, because without
it, the CLI will use empty token, this will pose issues for conversation
preprocessing. This IUT use get_random_token() method to obtains a new
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

import os
import logging
import binascii
from automation import COAP_SERVER_HOST, COAP_SERVER_PORT, COAP_CLIENT_HOST, LOG_LEVEL
from automation.automated_iut import AutomatedIUT, launch_short_automated_iut_process

default_coap_server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
coap_host_address = COAP_CLIENT_HOST
BASE_CMD = ["coap-client"]

logger = logging.getLogger()


def get_random_token():
    return binascii.hexlify(os.urandom(8))

# translates stimuli calls into IUT CLI calls
def get(base_url,
        resource,
        confirmable=True,
        use_token=True,
        accept_option=None,
        use_block_option=False,
        block_size=64,):
    cmd = BASE_CMD.copy()
    cmd += ['{url}{resource_path}'.format(url=base_url, resource_path=resource)]
    cmd += ['-m', 'GET']
    if accept_option:
        cmd += ['-A', accept_option]
    if not confirmable:
        cmd += ['-N']
    if use_token:
        tkn = get_random_token()
        cmd += ['-T', tkn]
    if use_block_option:
        block_option_val = '{start_number} {block_size}'.format(start_number=0, block_size=block_size)
        cmd += ['-b', str(block_option_val)]

    launch_short_automated_iut_process(cmd=cmd)


def put(base_url,
        resource,
        content_format="text/plain",
        confirmable=True,
        use_token=True,
        use_if_none_match=False,
        use_block_option=False,
        block_size=64,
        payload="my interop test payload",
        filepath_payload=None):
    """
    Note: if a file to send is specified with filepath_payload argument,
    the payload argument is ignored.
    """
    cmd = BASE_CMD.copy()
    cmd += ['{url}{resource_path}'.format(url=base_url, resource_path=resource)]
    cmd += ['-m', 'PUT', '-t', str(content_format)]
    if filepath_payload:
        cmd += ['-f', str(filepath_payload)]
    else:
        cmd += ['-e', str(payload)]
    if not confirmable:
        cmd += ['-N']
    if use_token:
        tkn = get_random_token()
        cmd += ['-T', str(tkn)]
    if use_if_none_match:
        cmd += ['-O', str(5)]
    if use_block_option:
        block_option_val = '{start_number} {block_size}'.format(start_number=0, block_size=block_size)
        cmd += ['-b', str(block_option_val)]

    launch_short_automated_iut_process(cmd=cmd)


def post(base_url,
         resource,
         content_format="text/plain",
         confirmable=True,
         use_token=True,
         use_block_option=False,
         block_size=64,
         payload="my interop test payload",
         filepath_payload=None):
    cmd = BASE_CMD.copy()
    cmd += ['{url}{resource_path}'.format(url=base_url, resource_path=resource)]
    cmd += ['-m', 'POST', '-t', str(content_format)]
    if filepath_payload:
        cmd += ['-f', filepath_payload]
    else:
        cmd += ['-e', payload]
    if not confirmable:
        cmd += ['-N']
    if use_token:
        tkn = get_random_token()
        cmd += ['-T', str(tkn)]
    if use_block_option:
        block_option_val = '{start_number} {block_size}'.format(start_number=0, block_size=block_size)
        cmd += ['-b', str(block_option_val)]

    launch_short_automated_iut_process(cmd=cmd)


def delete(base_url,
           resource,
           confirmable=True,
           use_token=True):
    cmd = BASE_CMD.copy()
    cmd += ['{url}{resource_path}'.format(url=base_url, resource_path=resource)]
    cmd += ['-m', 'DELETE']
    if not confirmable:
        cmd += ['-N']
    if use_token:
        tkn = get_random_token()
        cmd += ['-T', str(tkn)]

    launch_short_automated_iut_process(cmd=cmd)


def observe(base_url,
            resource,
            confirmable=True,
            use_token=True,
            duration=15):
    cmd = BASE_CMD.copy()
    cmd += ['{url}{resource_path}'.format(url=base_url, resource_path=resource)]
    cmd += ['-s', str(duration)]
    if not confirmable:
        cmd += ['-N']
    if use_token:
        tkn = get_random_token()
        cmd += ['-T', str(tkn)]

    launch_short_automated_iut_process(cmd=cmd, timeout=duration)


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


stimuli_to_libcoap_cli_call = {
    # CoAP CORE test cases stimuli
    "TD_COAP_CORE_01_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/test"}),
    "TD_COAP_CORE_02_step_01": (delete, {"base_url": default_coap_server_base_url, "resource": "/test"}),
    "TD_COAP_CORE_03_step_01": (put, {"base_url": default_coap_server_base_url, "resource": "/test", "content_format":"text/plain"}),
    "TD_COAP_CORE_04_step_01": (post, {"base_url": default_coap_server_base_url, "resource": "/test", "content_format":"text/plain"}),
    "TD_COAP_CORE_05_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/test", "confirmable":False}),
    "TD_COAP_CORE_06_step_01": (delete, {"base_url": default_coap_server_base_url,"resource": "/test", "confirmable":False}),
    "TD_COAP_CORE_07_step_01": (put, {"base_url": default_coap_server_base_url, "resource": "/test", "content_format":"text/plain","confirmable":False}),
    "TD_COAP_CORE_08_step_01": (post, {"base_url": default_coap_server_base_url, "resource": "/test", "content_format":"text/plain"}),
    "TD_COAP_CORE_09_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/separate"}),
    "TD_COAP_CORE_10_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/test"}),
    "TD_COAP_CORE_11_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/separate"}),
    "TD_COAP_CORE_12_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/test", "use_token":False}),
    "TD_COAP_CORE_13_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/seg1/seg2/seg3"}),
    "TD_COAP_CORE_14_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/query?first=1&second=2&third=3"}),
    "TD_COAP_CORE_15_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/test"}),
    "TD_COAP_CORE_16_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/separate"}),
    "TD_COAP_CORE_17_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/separate","confirmable":False}),
    "TD_COAP_CORE_18_step_01": (post, {"base_url": default_coap_server_base_url, "resource": "/test", "content_format":"text/plain"}),
    "TD_COAP_CORE_19_step_01": (post, {"base_url": default_coap_server_base_url, "resource": "/location-query?first=1&second=2&third=3"}),
    "TD_COAP_CORE_20_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/multi-format", "accept_option":"text/plain"}),
    "TD_COAP_CORE_20_step_05": (get, {"base_url": default_coap_server_base_url, "resource": "/multi-format", "accept_option":"application/xml"}),
    "TD_COAP_CORE_21_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/validate"}),
    "TD_COAP_CORE_22_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/validate"}),
    # "TD_COAP_CORE_22_step_04": "TD_COAP_CORE_22",
    "TD_COAP_CORE_22_step_08": (put, {"base_url": default_coap_server_base_url, "resource": "/validate"}),
    "TD_COAP_CORE_23_step_01": (put, {"base_url": default_coap_server_base_url, "resource": "/create1","content_format":"text/plain","use_if_none_match":True}),
    "TD_COAP_CORE_23_step_05": (put, {"base_url": default_coap_server_base_url, "resource": "/create1","content_format":"text/plain","use_if_none_match":True}),
    "TD_COAP_OBS_01_step_01":  (observe, {"base_url": default_coap_server_base_url, "resource": "/obs"}),
    "TD_COAP_OBS_02_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs-non","confirmable":False}),
    "TD_COAP_OBS_04_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs"}),
    "TD_COAP_OBS_05_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs"}),
    "TD_COAP_OBS_07_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs", "duration":20}),
    "TD_COAP_OBS_08_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs", "duration":20}),
    "TD_COAP_OBS_09_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs", "duration":20}),
    "TD_COAP_OBS_10_step_01": (observe, {"base_url": default_coap_server_base_url, "resource": "/obs", "duration":20}),
    # CoAP BLOCK test cases stimuli
    "TD_COAP_BLOCK_01_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/large","use_block_option":True}),
    "TD_COAP_BLOCK_02_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/large","use_block_option":False}),
    "TD_COAP_BLOCK_03_step_01": (put, {"base_url": default_coap_server_base_url, "resource": "/large-update","use_block_option":True, "content_format":"text/plain","payload": large_payload}),
    "TD_COAP_BLOCK_04_step_01": (post, {"base_url": default_coap_server_base_url, "resource": "/large-create","use_block_option":True, "content_format":"text/plain","payload": large_payload}),
    "TD_COAP_BLOCK_05_step_01": (post, {"base_url": default_coap_server_base_url, "resource": "/large-post","use_block_option":True, "content_format":"text/plain","payload": large_payload}),
    "TD_COAP_BLOCK_06_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/large","use_block_option":True,"block_size":16}),
    # CoAP LINK test cases stimuli
    "TD_COAP_LINK_01_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core"}),
    "TD_COAP_LINK_02_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?rt=Type1"}),
    "TD_COAP_LINK_03_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?rt=*"}),
    "TD_COAP_LINK_04_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?rt=Type2"}),
    "TD_COAP_LINK_05_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?if=If*"}),
    "TD_COAP_LINK_06_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?sz=*"}),
    "TD_COAP_LINK_07_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?href=/link1"}),
    "TD_COAP_LINK_08_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?href=/link*"}),
    "TD_COAP_LINK_09_step_01": (get, {"base_url": default_coap_server_base_url, "resource": "/.well-known/core?ct=40"}),
}

aux_stimuli_to_libcoap_cli_call = {
    "TD_COAP_OBS_07_step_07": (delete, {"base_url": default_coap_server_base_url, "resource": "/obs"}),

    # Update the /obs resource of with new payload having a different Content-format
    # Warning : We do assume that the former content format was NOT already application/xml
    # If not the test result will be inconclusive.
    "TD_COAP_OBS_08_step_07": (put, {"base_url": default_coap_server_base_url, "resource": "/obs", "content_format":"application/xml","payload":"My new payload with a new content-format."}),

    # Update the /obs resource of with new payload having the same Content-format
    # Warning : We do assume that the current content format was already text/plain
    # If not the test result will be inconclusive.
    "TD_COAP_OBS_09_step_07": (put, {"base_url": default_coap_server_base_url, "resource": "/obs", "content_format":"text/plain","payload":"My new payload with the same content-format."}),

    # unrelated GET
    "TD_COAP_OBS_10_step_07": (get, {"base_url": default_coap_server_base_url, "resource": "/obs"}),
}


class AutomatedLibcoapClient(AutomatedIUT):

    # CoAP CoRE
    implemented_testcases_list = ['TD_COAP_CORE_%02d' % tc for tc in range(1, 24)]
    # OBS
    implemented_testcases_list += ['TD_COAP_OBS_%02d' % tc for tc in range(1, 11)]
    # Link
    implemented_testcases_list += ['TD_COAP_LINK_%02d' % tc for tc in range(1, 10)]
    # BLOCK_01/BLOCK_06 are not yet implemented because the CLI do not allow to do early negotiation.
    implemented_testcases_list += ['TD_COAP_BLOCK_%02d' % tc for tc in range(2, 6)]

    component_id = 'automated_iut-coap_client-libcoap'
    node = 'coap_client'
    default_coap_server_base_url = 'coap://[%s]:%s' % (COAP_SERVER_HOST, COAP_SERVER_PORT)
    implemented_stimuli_list = list(stimuli_to_libcoap_cli_call.keys())
    implemented_aux_stimuli_list = list(aux_stimuli_to_libcoap_cli_call.keys())

    def __init__(self, mode_aux=False, target_base_url=None):
        """
        :param mode_aux: Defines if the libcoap implementation is actually an auxiliary component for running certain
        test cases steps that should be automatically run by framework instead of IUT
        :param target_base_url:
        """
        super().__init__(self.node)
        self.mode_aux = mode_aux

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
            if self.mode_aux:
                func, args = aux_stimuli_to_libcoap_cli_call[stimuli_step_id]
            else:
                func, args = stimuli_to_libcoap_cli_call[stimuli_step_id]
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
        iut = AutomatedLibcoapClient()
        iut.start()
        iut.join()
    except Exception as e:
        logger.error(e)
        exit(1)
