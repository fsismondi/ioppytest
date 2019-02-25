import json
import time
import tabulate
import logging
from messages import (MsgUiRequestSessionConfiguration,
                      MsgUiDisplay,
                      MsgUiRequestQuestionRadio,
                      MsgSniffingGetCaptureLast,
                      MsgSniffingGetCapture,
                      MsgUiSendFileToDownload,
                      MsgUiRequestConfirmationButton, )

from ioppytest.ui_adaptor import (UiResponseError,
                                  SessionError,
                                  WAITING_TIME_FOR_SECOND_USER,
                                  UI_TAG_SETUP, )


# auxiliary functions


def list_to_str(ls):
    """
    flattens a nested list up to two levels of depth

    :param ls: the list, supports str also
    :return: single string with all the items inside the list
    """

    ret = ''

    if ls is None:
        return 'None'

    if type(ls) is str:
        return ls

    try:
        for l in ls:
            if l and isinstance(l, list):
                for sub_l in l:
                    if sub_l and not isinstance(sub_l, list):
                        ret += str(sub_l) + ' \n '
                    else:
                        # I truncate in the second level
                        pass
            else:
                ret += str(l) + ' \n '

    except TypeError as e:
        return str(ls)
    return ret


def send_testcase_pcap_to_ui_file_for_download(amqp_publisher, testcase_id=None, user_id='all'):
    if testcase_id:
        resp = amqp_publisher.synch_request(MsgSniffingGetCapture(testcase_id=testcase_id))
    else:
        resp = amqp_publisher.synch_request(MsgSniffingGetCaptureLast())

    if resp is None:
        logging.error('Sniffer didnt respond to network traffic capture request.')
        return

    if not resp.ok:
        logging.error('Sniffer responded with error to network traffic capture request: %s' % resp)
        return

    m = MsgUiSendFileToDownload()
    m.routing_key = m.routing_key.replace('.all.', '.{}.'.format(user_id))
    m.fields = [
        {
            "name": resp.filename,
            "type": "data",
            "value": resp.value,
        }
    ]
    if testcase_id:
        m.tags = {"testcase": testcase_id}


def get_field_keys_from_ui_request(ui_message):
    """
    :return: list with all field names in request
    """

    fields_requested = [i['name'] for i in ui_message.fields if 'name' in i.keys()]
    return fields_requested


def get_field_keys_from_ui_reply(ui_message):
    """
    :return: list with all field names in reply
    """

    l = set()
    for item in ui_message.fields:
        l |= set(item.keys())
    return list(l)


def get_field_value_from_ui_reply(ui_message, field):
    for f in ui_message.fields:
        try:
            return f[field]
        except KeyError:
            pass

    return None


def get_session_configuration_from_ui(amqp_publisher):
    keys_to_validate = {"id", "configuration", "testSuite", "users"}

    resp = amqp_publisher.synch_request(MsgUiRequestSessionConfiguration())

    if resp is None:
        raise UiResponseError("Got session config None from UI")

    # (!) UI is not 100% compliant with specification and doesnt always answer with an ok field :/
    if hasattr(resp, 'ok') and not resp.ok:
        raise UiResponseError("Got NOK response from UI, response: %s" % repr(resp))

    resp_dict = resp.to_dict()

    if not keys_to_validate.issubset(resp_dict):
        raise UiResponseError("Expected minimum set of keys %s, Got  %s" % (keys_to_validate, resp_dict.keys()))

    return resp_dict


def get_current_users_online(amqp_publisher):
    session_configuration = get_session_configuration_from_ui(amqp_publisher)
    try:
        users = session_configuration['users']
        assert type(users) is list
        if "myslice" in users:
            users.remove("myslice")
        if "my_slice" in users:
            users.remove("my_slice")
        return users
    except TypeError:
        raise UiResponseError(
            "Session configuration messages received from UI doesnt contain <users> information : %s" % json.dumps(
                session_configuration, indent=4, sort_keys=True))


def wait_for_all_users_to_join_session(message_translator, amqp_publisher, session_configuration):
    shared_session = session_configuration and \
                     'shared' in session_configuration and \
                     session_configuration['shared'] is True
    expected_user_quantity = 2 if shared_session else 1

    if shared_session:

        if session_configuration is None:
            raise UiResponseError("Error trying to get session configuration from GUI, got empty configuration")

        # even if it's a non-updated session configuration, it must include at least one user!
        if 'users' not in session_configuration:
            raise UiResponseError(
                "No users information in UI's session configuration response %s" % repr(session_configuration))

        online_users = get_current_users_online(amqp_publisher)
        retries = 0
        max_retries = WAITING_TIME_FOR_SECOND_USER

        msg_text = "This is a User-to-User interop sesssion." \
                   "Please click on the 'share' button on the top-right corner of the GUI, " \
                   "then share the link with another F-Interop user so he/she can join the session"

        m = MsgUiDisplay(
            tags=UI_TAG_SETUP,
            level='info',
            fields=[
                {"type": "p",
                 "value": "%s" % msg_text},
            ])
        amqp_publisher.publish_ui_display(m)

        while len(online_users) < expected_user_quantity and retries <= max_retries:
            if retries % 60 == 0:
                mins_left = int((max_retries - retries) / 60)
                logging.info("Time left for second user to join %s" % mins_left)
                msg_text = "Waiting for at least 2 users to join the session (%s min. left)" % mins_left
                m = MsgUiDisplay(
                    tags=UI_TAG_SETUP,
                    fields=[
                        {"type": "p",
                         "value": "%s" % msg_text},
                    ])
                amqp_publisher.publish_ui_display(m)

            retries += 1
            time.sleep(1)  # do not modify time
            online_users = get_current_users_online(amqp_publisher)

        # got users connected or max retries
        if retries > max_retries:
            raise SessionError(
                'Waiting time for user to join has expired. Please RESTART session once users are ready to join')

        msg_text = "Users connected: %s . Ready to start the session" % str(online_users)
        logging.info(msg_text)
        m = MsgUiDisplay(
            tags=UI_TAG_SETUP,
            fields=[
                {"type": "p",
                 "value": "%s" % msg_text},
            ])
        amqp_publisher.publish_ui_display(m)


def display_in_ui_user_ids_and_roles(amqp_publisher, roles_to_user_mapping):
    # build UI message with roles
    fields = [{'type': 'p',
               'value': '%s' % tabulate.tabulate([[i, j] for i, j in roles_to_user_mapping.items()],
                                                 tablefmt="grid")}]

    m = MsgUiDisplay(
        title="Implementation under test (IUT) to User ID mapping:",
        tags=UI_TAG_SETUP,
        fields=fields
    )

    amqp_publisher.publish_ui_display(m)


def get_user_ids_and_roles_from_ui(message_translator, amqp_publisher, session_configuration):
    """ Returns dictionary roles_to_user_mapping

    Some assumptions:
     - maximum two users connected to session
     - users in the session are already connected
     - for a none SHARED_SESSION (single-user), method will try to create the dict mapping using session_configuration
     - for a SHARED_SESSION, were roles are [server_x,client_x], if user answers that he runs server_x then
     we assume client_x is an automated implementation

    for shared sessions, session_configuration should include "testsuite.additional_session_resource" field, e.g.:
    {
        'testsuite.additional_session_resource': 'automated_iut-coap_client-libcoap',
        'testsuite.testcases': [
            'http://doc.f-interop.eu/tests/TD_COAP_CORE_01',
            'http://doc.f-interop.eu/tests/TD_COAP_CORE_02'
        ]
    }

    :return: roles_to_user_mapping
    """

    # dict to return
    roles_to_user_mapping = {}

    # get connected/online users
    users = get_current_users_online(amqp_publisher)

    # get declared IUT roles from test suite message_translator object (e.g. [coap_client, coap_server])
    iut_roles = message_translator.get_iut_roles().copy()

    user_lead = users[0]
    try:
        second_user = users[1]
    except IndexError:  # not a shared session (shared session = user-to-user session)
        second_user = None

    if second_user is None:  # let's try to build mapping using "testsuite.additional_session_resource"
        if len(users) == 1:
            try:
                # auto_iut_resource_id will be our second_user name (as there's no second user connected)
                auto_iut_resource_id = session_configuration['configuration']["testsuite.additional_session_resource"]

                # let's assume that the info of the role is a substring of the additional_session_resource name
                if iut_roles[0] in auto_iut_resource_id:
                    roles_to_user_mapping[iut_roles[0]] = auto_iut_resource_id
                    roles_to_user_mapping[iut_roles[1]] = user_lead
                elif iut_roles[1] in auto_iut_resource_id:
                    roles_to_user_mapping[iut_roles[1]] = auto_iut_resource_id
                    roles_to_user_mapping[iut_roles[0]] = user_lead
                else:
                    logging.error("Cannot deduce IUT_role->user_id mapping from session_configuration information")

            except KeyError:
                logging.error(
                    "Single user connected but not additional_session_resource in "
                    "session_configuration: %s" % json.dumps(session_configuration, indent=4)
                )

        if roles_to_user_mapping:
            display_in_ui_user_ids_and_roles(amqp_publisher, roles_to_user_mapping)
            logging.info("IUT Role-> User ID map:\n%s" % json.dumps(roles_to_user_mapping, indent=4))
            return roles_to_user_mapping
        else:
            logging.info("Entering fallback mechanism for building roles_to_user_mapping ")

    # let's ask the user about the roles_to_user_mapping info
    fields = [
        {
            "type": "p",
            "value": "Which implementation under test (IUT) are you running? "
        }

    ]

    # put a radio entry per iut role
    for r in iut_roles:
        fields.append(
            {

                "name": 'iut_role',
                "type": "radio",
                "label": r,
                "value": r,
            }
        )

    # add also a 'ALL' roles option
    fields.append(
        {
            "name": 'iut_role',
            "type": "radio",
            "label": 'all',
            "value": 'all',
        }
    )

    m = MsgUiRequestQuestionRadio(
        tags=UI_TAG_SETUP,
        fields=fields
    )

    resp = amqp_publisher.synch_request(
        request=m,
        user_id=user_lead,
        timeout=120
    )

    try:
        user_lead_iut_role = resp.fields.pop()['iut_role']
    except:
        raise UiResponseError('received from the UI: %s' % repr(resp))

    # echo response back to *ALL* users
    m = MsgUiDisplay(
        tags=UI_TAG_SETUP,
        fields=[
            {
                "type": "p",
                "value": "User session owner ({user_name}) declared running IUT: {answer}".format(
                    user_name=user_lead,
                    answer=user_lead_iut_role
                )
            }
        ]
    )

    amqp_publisher.publish_ui_display(m)

    if user_lead_iut_role == "both":
        for r in iut_roles:
            roles_to_user_mapping[r] = user_lead
    else:
        roles_to_user_mapping[user_lead_iut_role] = user_lead
        # fill table with second entry iut_role_2->user_2
        iut_roles.remove(user_lead_iut_role)
        roles_to_user_mapping[iut_roles.pop()] = second_user if second_user else "automated_iut"

    display_in_ui_user_ids_and_roles(amqp_publisher, roles_to_user_mapping)

    return roles_to_user_mapping
