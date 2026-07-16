"""Maps each semicolon-delimited field of an *_ALL_APPS_GENERIC.log line to
a human-readable column name, used by evaluate.py.

The field order here is defined by SimLogger.java's genericResult1..6
string concatenation (search for those names in
src/edu/boun/edgecloudsim/utils/SimLogger.java to verify/extend this).
`reserved_unused(...)` entries are fields the Java code always writes as a
literal 0 -- not something evaluate.py can plot, but real, positional
fields in the log line that must stay accounted for so every later index
lines up correctly.
"""

all_apps_generic = {
    # genericResult1: ALL apps (indices 0-13)
    0: 'num_of_completed_tasks(ALL)',
    1: 'num_of_failed_tasks(ALL)',
    2: 'num_of_uncompleted_tasks(ALL)',
    3: 'num_of_failed_tasks_due_network(ALL)',
    4: 'average_service_time(ALL)_(sec)',
    5: 'average_processing_time(ALL)_(sec)',
    6: 'average_network_delay(ALL)_(sec)',
    7: 'reserved_unused(ALL)',
    8: 'average_cost',
    9: 'num_of_failed_tasks_due_vm_capacity(ALL)',
    10: 'num_of_failed_tasks_due_mobility(ALL)',
    11: 'average_QoE_for_executed(ALL)_(%)',
    12: 'average_QoE_for_all(ALL)_(%)',
    13: 'num_of_rejected_tasks_due_to_wlan_range(ALL)',
    # genericResult2: Edge (indices 14-22)
    14: 'num_of_completed_tasks(Edge)',
    15: 'num_of_failed_tasks(Edge)',
    16: 'num_of_uncompleted_tasks(Edge)',
    17: 'reserved_unused(Edge)',
    18: 'average_service_time(Edge)_(sec)',
    19: 'average_processing_time(Edge)_(sec)',
    20: 'reserved_unused(Edge)_2',
    21: 'average_server_utilization(Edge)_(%)',
    22: 'num_of_failed_tasks_due_vm_capacity(Edge)',
    # genericResult3: Cloud (indices 23-31)
    23: 'num_of_completed_tasks(Cloud)',
    24: 'num_of_failed_tasks(Cloud)',
    25: 'num_of_uncompleted_tasks(Cloud)',
    26: 'reserved_unused(Cloud)',
    27: 'average_service_time(Cloud)_(sec)',
    28: 'average_processing_time(Cloud)_(sec)',
    29: 'reserved_unused(Cloud)_2',
    30: 'average_server_utilization(Cloud)_(%)',
    31: 'num_of_failed_tasks_due_vm_capacity(Cloud)',
    # genericResult4: Mobile (indices 32-40)
    32: 'num_of_completed_tasks(Mobile)',
    33: 'num_of_failed_tasks(Mobile)',
    34: 'num_of_uncompleted_tasks(Mobile)',
    35: 'reserved_unused(Mobile)',
    36: 'average_service_time(Mobile)_(sec)',
    37: 'average_processing_time(Mobile)_(sec)',
    38: 'reserved_unused(Mobile)_2',
    39: 'average_server_utilization(Mobile)_(%)',
    40: 'num_of_failed_tasks_due_vm_capacity(Mobile)',
    # genericResult5: Network (indices 41-48)
    41: 'average_network_delay(LAN_delay)_(sec)',
    42: 'average_network_delay(MAN_delay)_(sec)',
    43: 'average_network_delay(WAN_delay)_(sec)',
    44: 'average_network_delay(GSM_delay)_(sec)',
    45: 'num_of_failed_tasks_due_network(WLAN)',
    46: 'num_of_failed_tasks_due_network(MAN)',
    47: 'num_of_failed_tasks_due_network(WAN)',
    48: 'num_of_failed_tasks_due_network(GSM)',
    # genericResult6: only appended to the ALL_APPS_GENERIC file itself (indices 49-50)
    # NOTE: index 49 is (endTime_ms - startTime_ms) / 60 in the Java source
    # (wall-clock System.currentTimeMillis() difference divided by 60, NOT
    # 60000) -- despite appearing next to "minutes" in some contexts, it is
    # NOT actual minutes. Named for what it truly is to avoid misreading it.
    49: 'scenario_wall_clock_time_(ms_div_60)',
    50: 'average_overhead(ns)',
}
