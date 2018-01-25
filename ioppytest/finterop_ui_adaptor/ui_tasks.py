import json
import time
import logging

from ioppytest.finterop_ui_adaptor import (UiResponseError,
                                           SessionError,
                                           MsgUiRequestSessionConfiguration,
                                           WAITING_TIME_FOR_SECOND_USER,
                                           MsgUiDisplay,
                                           MsgUiRequestConfirmationButton,
                                           SESSION_SETUP_TAG,
                                           )


# auxiliary functions
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

        while len(online_users) < expected_user_quantity and retries <= max_retries:
            msg_text = "Waiting for at least 2 users to join the session, retries : %s / %s" % (retries, max_retries)
            m = MsgUiDisplay(
                tags=SESSION_SETUP_TAG,
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
            tags=SESSION_SETUP_TAG,
            fields=[
                {"type": "p",
                 "value": "%s" % msg_text},
            ])
        amqp_publisher.publish_ui_display(m)


def get_user_ids_and_roles_from_ui(message_translator, amqp_publisher, session_configuration):
    roles_to_user_mapping = {}
    users = get_current_users_online(amqp_publisher)
    # ToDo fixme! I'm assuming there's only 2 users max for these method
    assert len(users) == 2, 'got user list: %s' % users

    # let's just ask to the user number which are the user IUTs roles
    user_lead = users[0]
    second_user = users[1]
    iut_roles = message_translator.get_iut_roles()
    for iut_role in iut_roles:
        m = MsgUiRequestConfirmationButton(
            tags=SESSION_SETUP_TAG,
            title="Is it you (%s) driving implementation under test (IUT) : %s? " % (user_lead, iut_role),
            fields=[
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
            ]
        )
        resp = amqp_publisher.synch_request(
            request=m,
            user_id=user_lead,
            timeout=50
        )

        # echo response back to users
        m = MsgUiDisplay(
            tags=SESSION_SETUP_TAG,
            fields=[
                {"type": "p",
                 "value": "Got : %s" % repr(resp)},
            ])

        amqp_publisher.publish_ui_display(m)

        if resp and resp.ok and 'yes' in str(resp.fields):
            logging.info({iut_role, user_lead})
            roles_to_user_mapping[iut_role] = user_lead
        elif resp and resp.ok and 'no' in str(resp.fields):
            roles_to_user_mapping[iut_role] = second_user
        else:
            raise UiResponseError('received from the UI: %s' % repr(resp))

        logging.info("Roles to user mapping updated: %s" % roles_to_user_mapping)

    return roles_to_user_mapping
