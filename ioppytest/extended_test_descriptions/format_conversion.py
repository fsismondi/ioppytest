import os
import yaml
import logging
import textwrap

from ioppytest import (
    TEST_DESCRIPTIONS,
    TEST_DESCRIPTIONS_CONFIGS,
    RESULTS_DIR,
    AUTO_DISSECTION_FILE,
    PROJECT_DIR,
    LOG_LEVEL
)

from ioppytest.test_coordinator.testsuite import TestCase, TestConfig

from ioppytest.utils import tabulate

tabulate.PRESERVE_WHITESPACE = True

COMPONENT_ID = 'webserver'

logger = logging.getLogger(COMPONENT_ID)
logger.setLevel(LOG_LEVEL)

td_list = list()
td_dict = dict()

td_config_list = list()
td_config_dict = dict()
TABLE_STYLE_MARKDOWN = 'grid'  # either grid or
TABLE_STYLE_HTML = 'html'  # either grid or
FILENAME_HTML_REPORT = 'testsuite_results.html'
STEP_COLUMN_IDENTATION = 4

tail = """
"mantainer": "Federico Sismondi",
"mantainer_email": "federico.sismondi@inria.fr"

if you spotted any errors or you want to comment on sth don't hesitate to contact me.
"""

for TD in TEST_DESCRIPTIONS + TEST_DESCRIPTIONS_CONFIGS:
    with open(TD, "r", encoding="utf-8") as stream:
        yaml_docs = yaml.load_all(stream)
        for yaml_doc in yaml_docs:
            if type(yaml_doc) is TestCase:
                td_list.append(yaml_doc)
                td_dict[yaml_doc.id] = yaml_doc
            elif type(yaml_doc) is TestConfig:
                td_config_list.append(yaml_doc)
                td_config_dict[yaml_doc.id] = yaml_doc
            else:
                logging.warning("Unrecognised yaml structure: %s" % str(yaml_doc))


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
    testcase = td_dict[testcase_id.upper()]
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


def get_markdown_representation_of_testcase_configuration(testcase_config_id: str):
    assert type(testcase_config_id) is str

    table = []
    header_fields = [
        ('id', 'Tescase Config ID'),
        ('uri', 'Testcase Config URL'),
        ('nodes_description', 'Nodes'),
        ('topology', 'Topology'),
        ('default_addressing', 'Addressing'),
        ('configuration_diagram', 'Diagram'),
    ]

    # first let's add the header
    testcase = td_config_dict[testcase_config_id.upper()]
    for i in header_fields:
        col1 = i[1]
        col2 = getattr(testcase, i[0])
        col2 = list_to_str(col2)  # flattens info
        table.append([col1, col2])

    return tabulate.tabulate(table, tablefmt=TABLE_STYLE_MARKDOWN)


def get_html_representation_of_testcase(testcase_id):
    l = [(list_to_str(item[0]), list_to_str(item[1])) for item in td_dict[testcase_id].to_dict(verbose=True).items()]
    return tabulate.tabulate(l, tablefmt=TABLE_STYLE_HTML)


if __name__ == '__main__':
    from ioppytest import TMPDIR

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

    print(td_config_list)
    for i in td_config_list:
        print(i.id)
        print(get_markdown_representation_of_testcase_configuration(i.id))