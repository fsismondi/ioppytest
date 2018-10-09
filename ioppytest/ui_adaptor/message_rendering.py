from tabulate import tabulate
from ioppytest import LOG_LEVEL, LOGGER_FORMAT
import textwrap
import logging
import traceback

# init logging to stnd output and log files
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)


def list_to_str(ls, max_width=79):
    """
    flattens a nested list up to two levels of depth

    :param ls: the list, supports str also
    :param max_width: max width of each text line (inserts \n if line is longer)
    :return: single string with all the items inside the list
    """

    ret = ''

    if ls is None:
        return 'None'

    if type(ls) is str:
        return textwrap.fill(ls, width=max_width)

    try:
        for l in ls:
            if l and isinstance(l, list):  # there's a list inside the list
                for sub_l in l:
                    if sub_l and not isinstance(sub_l, list):
                        ret += "    - " + textwrap.fill(str(sub_l), width=max_width) + '\n'
                    else:
                        # I truncate in the second level
                        pass
            else:
                ret += "- " + textwrap.fill(str(l), width=max_width) + '\n'

    except TypeError as e:
        logger.error(e)
        return str(ls)

    return ret


def testsuite_results_to_ascii_table(testcases_results: list):
    """
    :param tc_resutls: list of test cases results
    :return: string-based (ascii chars) table of all results
    """

    # add header
    summary_table = [["Testcase ID", "Verdict", "Description"]]

    for tc_report in testcases_results:
        assert type(tc_report) is dict

        # add report basic info as a raw into the summary_table
        try:
            summary_table.append(
                [
                    tc_report['testcase_id'],
                    tc_report['verdict'],
                    list_to_str(tc_report['description'])
                ]
            )
        except KeyError:
            logger.warning("Couldnt parse: %s" % str(tc_report))
            summary_table.append([tc_report['testcase_id'], "None", "None"])

    return tabulate(summary_table, tablefmt="grid", headers="firstrow")


def testsuite_state_to_ascii_table(state_dict: dict):
    """
    :param state_dict: dict of session info, see example
    :return: string-based (ascii chars) table of all states

    example of state dict:

    {
    "configuration": null,
    "ok": true,
    "session_id": null,
    "started": true,
    "step_id": null,
    "tc_list": [
        {
            "testcase_id": "TD_COAP_CORE_01",
            "testcase_ref": "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
            "state": "finished",
            "objective": "Perform GET transaction(CON mode)"
        },
        {
            "testcase_id": "TD_COAP_CORE_02",
            "testcase_ref": "http://doc.f-interop.eu/tests/TD_COAP_CORE_02",
            "state": "finished",
            "objective": "Perform DELETE transaction (CON mode)"
        },
        {
            "testcase_id": "TD_COAP_CORE_23",
            "testcase_ref": "http://doc.f-interop.eu/tests/TD_COAP_CORE_23",
            "state": "configuring",
            "objective": "Perform PUT transaction containing the If-None-Match option (CON mode)"
        },
        {
            "testcase_id": "TD_COAP_CORE_31",
            "testcase_ref": "http://doc.f-interop.eu/tests/TD_COAP_CORE_31",
            "state": null,
            "objective": "Perform CoAP Ping (CON mode)"
        }
    ],
    "testcase_id": "TD_COAP_CORE_23",
    "testcase_state": "configuring",
    "users": null
}
    """
    assert type(state_dict) is dict

    table_keys = ['session_id', 'configuration', 'started', 'testcase_id', 'testcase_state']
    table_dict = {key: state_dict[key] for key in table_keys}

    return tabulate(table_dict, tablefmt="grid")


def testcase_verdict_to_ascii_table(testcase_verdict_report):
    """
    returns a stringed based description of MsgTestCaseVerdict

    example of input report:
    {
        "description": "premature end of conversation",
        "objective": "Perform GET transaction(CON mode)",
        "partial_verdicts": [
            [
                "TD_COAP_CORE_01_step_02",
                null,
                "CHECK step: postponed",
                ""
            ],
            [
                "TD_COAP_CORE_01_step_03",
                null,
                "CHECK step: postponed",
                ""
            ],
            [
                "TD_COAP_CORE_01_step_04",
                "pass",
                "VERIFY step: User informed that the information was displayed correclty on his/her IUT",
                ""
            ],
            [
                "tat_check_1",
                "pass",
                "<Frame   3: [bbbb::1 -> bbbb::2] CoAP [CON 324] GET /test> Match: CoAP(type=0, code=1)"
            ],
            [
                "tat_check_2",
                "inconclusive",
                "premature end of conversation"
            ]
        ],
        "pre_conditions": [
            "Server offers the resource /test with resource content is not empty that handles GET with an arbitrary payload"
        ],
        "state": "finished",
        "testcase_id": "TD_COAP_CORE_01",
        "testcase_ref": "http://doc.f-interop.eu/tests/TD_COAP_CORE_01",
        "verdict": "inconclusive"
    }

    """
    try:
        partial_verdict = testcase_verdict_report.pop('partial_verdicts')
    except KeyError:
        partial_verdict = None
        logger.warning("No partial_verdicts for TC: %s" % testcase_verdict_report['testcase_id'])

    table = list()
    table_frames = []
    table_partial_verdicts = []
    ret_string = ""

    step_message_fields = [
        ('verdict', 'Verdict'),
        ('description', 'Verdict info'),
        ('testcase_id', 'Test case ID'),
        ('objective', 'Test Purpose'),
        ('testcase_ref', 'Test case URL'),
        ('pre_conditions', 'Pre-conditions'),

    ]

    for i in step_message_fields:
        try:
            col1 = i[1]
            col2 = testcase_verdict_report[i[0]]
            col2 = list_to_str(col2)  # flattens info
            table.append([col1, col2])
        except KeyError as e:
            logger.warning(e)

    ret_string += "\n === Verdict info ==="
    ret_string += "\n"
    ret_string += tabulate(table, tablefmt="grid")

    # 'warning' is yellow, 'highlighted' is green, and 'error' is red
    if 'verdict' in testcase_verdict_report and 'pass' in testcase_verdict_report['verdict']:
        display_color = 'highlighted'
    elif 'verdict' in testcase_verdict_report and 'fail' in testcase_verdict_report['verdict'].lower():
        display_color = 'error'
    elif 'verdict' in testcase_verdict_report and 'error' in testcase_verdict_report['verdict'].lower():
        display_color = 'error'
    elif 'verdict' in testcase_verdict_report and 'none' in testcase_verdict_report['verdict'].lower():
        display_color = 'error'
    else:
        display_color = 'warning'

    if partial_verdict:
        table_partial_verdicts.append(('Step ID', 'Partial \nVerdict', 'Description'))
        for item in partial_verdict:
            try:
                assert type(item) is list
                try:
                    cell_1 = item.pop(0)
                    cell_2 = item.pop(0)
                    cell_3 = list_to_str(item)
                    table_partial_verdicts.append((cell_1, cell_2, cell_3))
                except IndexError:
                    logger.error("Index error trying to parse : %s" % str(item))

                if 'Frame' in list_to_str(item):
                    table_frames.append(item)

            except Exception as e:
                logger.error(e)
                logger.error(traceback.format_exc())
                break

    # ret_string += "\n === Partial verdicts ==="
    # ret_string += "\n"
    # ret_string += tabulate(table_partial_verdicts, tablefmt="grid")


    ret_string += "\n === Frames info ==="
    ret_string += "\n"
    ret_string += tabulate(table_frames, tablefmt="grid")

    return ret_string, display_color
