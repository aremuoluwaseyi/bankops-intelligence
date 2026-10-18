"""Controlled synthetic incident definitions for BankOps Intelligence.

These are ground-truth test scenarios, not real banking incidents.
"""

INCIDENT_SCENARIOS = [
    {"incident_id":"INC001","name":"External Payment Provider Degradation","affected_services":["S001"],"component_id":"C003","error_code":"GW_TIMEOUT","health_state":"DEGRADED"},
    {"incident_id":"INC002","name":"OTP Provider Degradation","affected_services":["S003","S004"],"component_id":"C004","error_code":"OTP_TIMEOUT","health_state":"DEGRADED"},
    {"incident_id":"INC003","name":"Operational Database Slowdown","affected_services":["S003","S007"],"component_id":"C006","error_code":"DB_TIMEOUT","health_state":"UP"},
    {"incident_id":"INC004","name":"Bill Payment Provider Degradation","affected_services":["S005"],"component_id":"C008","error_code":"BILLER_TIMEOUT","health_state":"DEGRADED"},
    {"incident_id":"INC005","name":"Post-Deployment Payment Service Regression","affected_services":["S001","S002","S005","S006"],"component_id":"C001","error_code":"APP_500","health_state":"UP"},
]
