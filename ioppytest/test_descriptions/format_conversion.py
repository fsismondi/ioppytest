import logging
import logging
import textwrap

from ioppytest import (
    LOG_LEVEL
)
from ioppytest.test_suite import (get_dict_of_all_test_cases,
                                  get_dict_of_all_test_cases_configurations)
from ioppytest.utils import tabulate

tabulate.PRESERVE_WHITESPACE = True

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

TABLE_STYLE_MARKDOWN = 'grid'  # either grid or
TABLE_STYLE_HTML = 'html'  # either grid or
FILENAME_HTML_REPORT = 'testsuite_results.html'
STEP_COLUMN_IDENTATION = 4

tail = """
"mantainer": "Federico Sismondi",
"mantainer_email": "federico.sismondi@inria.fr"

if you spotted any errors or you want to comment on sth don't hesitate to contact me.
"""


def count_max_row_length(items_to_count, initial_count=0):
    if type(items_to_count) is str:
        if "\n" in items_to_count:
            print("Function doesnt handle multi-line cells")
            # do not count anything here
        else:
            initial_count += len(items_to_count)
    elif type(items_to_count) is list:
        for i in items_to_count:
            initial_count = count_max_row_length(i, initial_count)
    elif type(items_to_count) is tuple:
        for i in items_to_count:
            initial_count = count_max_row_length(i, initial_count)
    else:
        raise Exception("cannot handle type %s" % type(items_to_count))
    return initial_count


def list_to_str(ls, max_width=200):
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
            if l and isinstance(l, list):  # there's a list inside the list
                for sub_l in l:
                    if sub_l and not isinstance(sub_l, list):
                        ret += "    - " + textwrap.fill(str(sub_l), width=max_width) + '\n'
                    else:
                        # I truncate in the second level
                        pass
            elif l and isinstance(l, dict):
                for tup in l.items():
                    ret += "    - " + textwrap.fill("%s: %s" % tup, width=max_width) + '\n'
            else:
                ret += "- " + textwrap.fill(str(l), width=max_width) + '\n'

    except TypeError as e:
        logger.error(e)
        return str(ls)

    return ret


def get_markdown_representation_of_testcase(testcase_id: str):
    assert type(testcase_id) is str

    def build_step_cell(step_id, step_type, step_info):
        cell = "{step_type} - {step_id}\n\n".format(step_type=step_type.upper(), step_id=step_id)
        for item in step_info.split('\n'):
            cell += "{indentation}{step_info_line}\n".format(indentation=" " * STEP_COLUMN_IDENTATION,
                                                             step_info_line=item)
        return cell

    table = []
    header_fields = [
        ('id', 'Tescase ID'),
        ('uri', 'Testcase URL'),
        ('objective', 'Test Purpose'),
        ('configuration_id', 'Configuration ID'),
        ('references', 'References'),
        ('pre_conditions', 'Preconditions'),
        ('notes', 'Notes'),
    ]

    # first let's add the header
    testcase = get_dict_of_all_test_cases()[testcase_id.upper()]
    for i in header_fields:
        col1 = i[1]
        col2 = getattr(testcase, i[0])
        col2 = list_to_str(col2)  # flattens info
        table.append([col1, col2])

    # let's add the test sequence (steps)
    table.append(["Test Sequence", " " * 200])
    for step in testcase.sequence:
        table.append(["", build_step_cell(step.id, step.type, list_to_str(step.description))])

    return tabulate.tabulate(table, tablefmt=TABLE_STYLE_MARKDOWN)


def get_markdown_representation_of_testcase_configuration(testcase_config_id: str, include_diagram=False):
    assert type(testcase_config_id) is str

    td_config_dict = get_dict_of_all_test_cases_configurations()
    testcase = td_config_dict[testcase_config_id.upper()]

    table = []
    header_fields = [
        ('id', 'Config ID'),
        ('uri', 'Config URL'),
    ]

    # first let's add the header
    for i in header_fields:
        col1 = i[1]
        col2 = getattr(testcase, i[0])
        col2 = list_to_str(col2)  # flattens info
        table.append([col1, col2])

    # process special fields (list of list and list of dicts)
    for sub_field in getattr(testcase, 'nodes_description'):
        table.append(["Config \ndescription\n(%s)" % sub_field['node'], list_to_str(sub_field['message'])])

    for sub_field in getattr(testcase, 'default_addressing'):
        table.append(
            ["Node address  \n(%s)" % sub_field['node'], "%s:%s" % (sub_field['ipv6_prefix'], sub_field['ipv6_host'])])

    ascii_table = tabulate.tabulate(table, tablefmt=TABLE_STYLE_MARKDOWN)

    # include diagram if requested
    if include_diagram:
        ascii_table += "\n\n"
        ascii_table += "Configuration diagram\n"
        try:
            ascii_table += getattr(testcase, 'configuration_diagram')
        except TypeError:
            logger.warning('Test config doesnt have any diagram')

    return ascii_table


def get_html_representation_of_testcase(testcase_id):
    td_dict = get_dict_of_all_test_cases()
    l = [(list_to_str(item[0]), list_to_str(item[1])) for item in td_dict[testcase_id].to_dict(verbose=True).items()]
    return tabulate.tabulate(l, tablefmt=TABLE_STYLE_HTML)


if __name__ == '__main__':

    # # one .md per TC
    # for i in td_list:
    #     if "6LOWPAN" in i.id:
    #         with open(os.path.join(TMPDIR, i.id + '.md'), 'w') as test_case_md_file:
    #             test_case_md_file.write(get_markdown_representation_of_testcase(i.id))
    #
    #             # for i in td_list:
    #             #     with open(os.path.join(TMPDIR, i.id + '.html'), 'w') as test_case_md_file:
    #             #         test_case_md_file.write(get_html_representation_of_testcase(i.id))

    # # one .md for all TC
    # testsuite_filename = 'TD_6LoWPAN_interoperability.md'
    # with open(os.path.join(TMPDIR, testsuite_filename), 'w') as test_case_md_file:
    #
    #     for i in td_list:
    #         if "6LOWPAN" in i.id:
    #             test_case_md_file.write("# Interoperability Test Description: %s\n" % i.id)
    #             test_case_md_file.write(get_markdown_representation_of_testcase(i.id))
    #             test_case_md_file.write("\n\n")
    #
    #     for i in td_list:
    #         if "6LOWPAN" in i.id:
    #             print("\n{\n'value': 'http://doc.f-interop.eu/tests/%s'\n},"%i.id)

    # print(td_config_list)
    # for i in td_config_list:
    #     print(i.id)
    #     print(get_markdown_representation_of_testcase_configuration(i.id))

    for TD in TEST_DESCRIPTIONS + TEST_DESCRIPTIONS_CONFIGS:
        print(type(TD))
        print(TD)
