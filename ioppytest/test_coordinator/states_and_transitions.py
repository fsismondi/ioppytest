STEP_TIMEOUT = 6000  # seconds   # TODO test suite or test coordinator param?
IUT_CONFIGURATION_TIMEOUT = 5  # seconds # TODO test suite or test coordinator param?

states = [
    {
        'name': 'null',
        'on_enter': ['bootstrap'],
        'on_exit': [],
        'tags': []
    },
    {
        'name': 'bootstrapping',
        'on_enter': ['handle_bootstrap'],
        'on_exit': ['notify_testsuite_ready'],
        'tags': ['busy']
    },
    {
        'name': 'waiting_for_testsuite_config',
        'on_enter': [],
        'on_exit': ['notify_testsuite_configured']
    },
    {
        'name': 'waiting_for_testsuite_start',
        'on_enter': [],
        'on_exit': ['notify_testsuite_started']
    },
    {
        'name': 'preparing_next_testcase',  # dummy state used for factorizing several transitions
        'on_enter': ['_prepare_next_testcase'],
        'on_exit': []
    },
    {
        'name': 'waiting_for_iut_configuration_executed',
        'on_enter': [],  # do not notify here, we will enter this state least two times
        'on_exit': [],
        'timeout': IUT_CONFIGURATION_TIMEOUT,
        'on_timeout': '_timeout_waiting_iut_configuration_executed'
    },
    {
        'name': 'waiting_for_testcase_start',
        'on_enter': [],
        'on_exit': [],
        # for ignoring "Can't trigger event _all_iut_configuration_executed from state waiting_for_testcase_start!"
        'ignore_invalid_triggers': True
    },
    {
        'name': 'preparing_next_step',  # dummy state used for factorizing several transitions
        'on_enter': ['_prepare_next_step'],
        'on_exit': []
    },
    {
        'name': 'waiting_for_step_executed',
        'on_enter': ['notify_step_execute'],
        'on_exit': [],
        # 'timeout': STEP_TIMEOUT,
        # 'on_timeout': '_timeout_waiting_step_executed'
    },
    {
        'name': 'testcase_finished',
        'on_enter': [
            'notify_testcase_finished',
            'generate_testcases_verdict',
            'notify_testcase_verdict',
            'to_preparing_next_testcase'],  # jumps to following state, this makes testcase_finished a transition state
        'on_exit': []
    },
    {
        'name': 'testcase_aborted',
        'on_enter': ['notify_testcase_aborted'],
        'on_exit': []
    },
    {
        'name': 'testsuite_finished',
        'on_enter': ['handle_finish_testsuite',
                     'notify_testsuite_finished',
                     ],
        'on_exit': []
    },
]
transitions = [
    {
        'trigger': 'bootstrap',
        'source': 'null',
        'dest': 'bootstrapping'
    },
    {
        'trigger': '_bootstrapped',
        'source': 'bootstrapping',
        'dest': 'waiting_for_testsuite_config'
    },
    {
        'trigger': 'configure_testsuite',
        'source': 'waiting_for_testsuite_config',
        'dest': 'waiting_for_testsuite_start',
        'before': [
            '_set_received_event',
            'handle_testsuite_config'
        ]
    },
    {
        'trigger': 'start_testsuite',
        'source': ['waiting_for_testsuite_start',
                   'waiting_for_testsuite_config'],
        'dest': 'preparing_next_testcase',
        'before': [
            '_set_received_event',
            'handle_testsuite_start',
            'configure_agent_data_plane_interfaces'
        ]
    },
    {
        'trigger': '_start_configuration',
        'source': 'preparing_next_testcase',
        'dest': 'waiting_for_iut_configuration_executed',
        'after': 'notify_tescase_configuration'
    },
    {
        'trigger': '_finish_testsuite',
        'source': 'preparing_next_testcase',
        'dest': 'testsuite_finished',
    },
    {
        'trigger': 'iut_configuration_executed',
        'source': '*',
        'dest': '=',
        'before': ['_set_received_event'],
        'after': ['handle_iut_configuration_executed']
    },
    {
        'trigger': 'start_testcase',
        'source': [
            'waiting_for_testcase_start',
            'waiting_for_iut_configuration_executed'  # start tc and skip iut configuration executed is allowed
        ],
        'dest': 'preparing_next_step',
        'before': [
            '_set_received_event',
            'handle_start_testcase'
        ],
        'after': [
            'notify_testcase_started'
        ]
    },
    {
        'trigger': '_start_next_step',
        'source': 'preparing_next_step',
        'dest': 'waiting_for_step_executed',
    },
    {
        'trigger': '_finish_testcase',
        'source': 'preparing_next_step',
        'dest': 'testcase_finished',
        'before': [
            '_set_received_event',
            'handle_finish_testcase'
        ]
    },
    {
        'trigger': 'abort_testcase',
        'source': [
            'waiting_for_iut_configuration_executed',
            'preparing_next_step',
            'waiting_for_testcase_start',
            'waiting_for_step_executed',
        ],
        'dest': 'preparing_next_testcase',
        'before': [
            '_set_received_event',
            'handle_abort_testcase'
        ]
    },
    {
        'trigger': 'step_executed',
        'source': 'waiting_for_step_executed',
        'dest': 'preparing_next_step',
        'before': [
            '_set_received_event',
            'handle_step_executed'
        ],
    },
    {
        'trigger': '_timeout_waiting_iut_configuration_executed',
        'source': 'waiting_for_iut_configuration_executed',
        'dest': 'waiting_for_testcase_start',
        'before': '_set_received_event',
        'after': 'notify_testcase_ready'
    },
    {
        'trigger': '_all_iut_configuration_executed',
        'source': 'waiting_for_iut_configuration_executed',
        'dest': 'waiting_for_testcase_start',
        'before': '_set_received_event',
        'after': 'notify_testcase_ready'
    },
    {
        'trigger': '_timeout_waiting_step_executed',
        'source': 'waiting_for_step_executed',
        'dest': 'waiting_for_testsuite_start',
        'before': [
            '_set_received_event',
            'handle_current_step_timeout'
        ]
    },

    # NOTE: if the FSM already advanced to next test case, then restart_testcase cannot be used,
    # select_test_case should be used instead

    {
        'trigger': 'restart_testcase',
        'source': [
            'waiting_for_iut_configuration_executed',
            'waiting_for_testcase_start',
            'waiting_for_step_executed',
            'testcase_finished',
        ],
        'dest': 'preparing_next_testcase',
        'before': [
            '_set_received_event',
            'handle_testcase_restart'
        ]
    },
    {
        'trigger': 'select_testcase',
        'source': [
            'waiting_for_iut_configuration_executed',
            'waiting_for_testcase_start',
            'waiting_for_step_executed',
            'testcase_finished'
        ],
        'dest': 'preparing_next_testcase',
        'before': [
            '_set_received_event',
            'handle_testcase_select'
        ]
    },
    # SKIP test case, opt1 : is_skipping_current_testcase
    {
        'trigger': 'skip_testcase',
        'source': [
            'waiting_for_iut_configuration_executed',
            'waiting_for_testcase_start',
            'waiting_for_step_executed',
            'testcase_finished'
        ],
        'dest': 'preparing_next_testcase',
        'conditions': 'is_skipping_current_testcase',
        'before': [
            '_set_received_event',
            'handle_testcase_skip'
        ]
    },
    # SKIP test case, opt2 : not is_skipping_current_testcase
    {
        'trigger': 'skip_testcase',
        'source': [
            'waiting_for_iut_configuration_executed',
            'waiting_for_testcase_start',
            'waiting_for_testsuite_config',
            'waiting_for_step_executed',
            'testcase_finished'
        ],
        'dest': '=',
        'unless': 'is_skipping_current_testcase',
        'before': [
            '_set_received_event',
            'handle_testcase_skip'
        ]
    },

    {
        'trigger': 'go_to_next_testcase',
        'source': [],
        'dest': '=',
        'before': '_set_received_event'
    },
]
