import json
import time
import logging

from ioppytest.finterop_ui_adaptor import (UiResponseError,
                                           SessionError,
                                           MsgUiRequestSessionConfiguration,
                                           WAITING_TIME_FOR_SECOND_USER,
                                           MsgUiDisplay,
                                           MsgUiRequestConfirmationButton,
                                           UI_TAG_SETUP,
                                           )


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

    if not resp.ok:
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

        msg_text = "Please click on the 'share' button on the top-right corner of the GUI, " \
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


def get_user_ids_and_roles_from_ui(message_translator, amqp_publisher, session_configuration):
    roles_to_user_mapping = {}
    users = get_current_users_online(amqp_publisher)

    # let's just ask to the user number 1 which are the user IUTs roles
    user_lead = users[0]
    try:
        second_user = users[1]
    except IndexError:
        second_user = None

    iut_roles = message_translator.get_iut_roles()
    for iut_role in iut_roles:
        m = MsgUiRequestConfirmationButton(
            tags=UI_TAG_SETUP,
            fields=[
                {
                    "type": "p",
                    "value": "%s runs implementation under test (IUT) with role: %s? "
                             % (user_lead.upper(), iut_role.upper())
                },
                {
                    "name": "yes",
                    "type": "button",
                    "value": True
                },
                {
                    "name": "no",
                    "type": "button",
                    "value": True
                },
            ],
        )
        resp = amqp_publisher.synch_request(
            request=m,
            user_id=user_lead,
            timeout=120
        )

        if resp and resp.ok and 'yes' in str(resp.fields):
            user_answer = True
        elif resp and resp.ok and 'no' in str(resp.fields):
            user_answer = False
        else:
            raise UiResponseError('received from the UI: %s' % repr(resp))

        # echo response back to users
        m = MsgUiDisplay(
            tags=UI_TAG_SETUP,
            fields=[
                {"type": "p",
                 "value": "{user_name} reply: {user_name} runs IUT with role {iut_role}: {answer}".format(
                     user_name=user_lead,
                     iut_role=iut_role.upper(),
                     answer=str(user_answer).upper()
                 )}
            ])

        amqp_publisher.publish_ui_display(m)

        # ToDo fixme! I'm assuming there's only 2 users max for these method
        if user_answer:
            roles_to_user_mapping[iut_role] = user_lead
        else:
            roles_to_user_mapping[iut_role] = second_user

        logging.info("Roles to user mapping updated: %s" % roles_to_user_mapping)

    return roles_to_user_mapping
