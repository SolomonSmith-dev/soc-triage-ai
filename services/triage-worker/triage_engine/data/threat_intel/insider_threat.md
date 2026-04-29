# Insider Threat Indicators

Insider threats include malicious insiders, compromised insiders, and negligent insiders. Detection requires behavioral baselining rather than signature matching.

## Behavioral Indicators
- Off-hours access patterns inconsistent with role
- Access to systems or data outside job function
- Bulk download or copy operations
- Use of personal cloud storage from corporate devices
- Removable media usage in restricted environments
- Email forwarding rules to external addresses
- Searches for sensitive data unrelated to current work

## High-Risk Life Events
- Employee on performance improvement plan
- Recent termination notice or resignation
- Recent demotion or denied promotion
- Financial distress indicators in HR data
- Recent grievance or workplace conflict

## Departing Employee Signals
- Increased file access in final two weeks
- Mass downloads of customer lists, source code, design documents
- Connecting personal devices
- Forwarding work email to personal accounts
- Attempting to access systems they will lose access to
- Communicating with competitor email domains

## Privileged User Risks
Administrators have elevated risk profile because their actions blend into normal admin work. Indicators include:
- Use of personal accounts for administrative tasks (avoiding audit)
- Disabling logging or monitoring on systems they administer
- Creating accounts outside normal provisioning
- Accessing data unrelated to admin duties (browsing user files)
- Off-hours administrative activity without change tickets

## Compromised Insider Indicators
Distinguishing compromise from malice requires checking:
- Geographic anomalies (login from country employee is not in)
- Impossible travel (logins from distant locations within short time window)
- New device fingerprints
- Authentication method changes (legacy auth where modern was previously used)
- Behavior change beyond gradual baseline drift

## MITRE Mapping
T1078 Valid Accounts, T1530 Data from Cloud Storage Object, T1567 Exfiltration Over Web Service, T1114 Email Collection.

## Triage Guidance
Insider threat alerts are sensitive and high-stakes. False positives damage trust. Recommended approach: never confront the user directly, escalate to HR and Legal before any action, preserve evidence with forensic integrity, work with security leadership for containment decisions, and maintain operational security in the investigation. Never tip off the subject through unusual activity or questions to coworkers.

Severity classification:
- Critical: active exfiltration of regulated data, sabotage of production systems, or confirmed account compromise of privileged user
- High: bulk download of sensitive data, off-hours privileged access without justification, or HR-flagged user with anomalous activity
- Medium: behavior outside baseline without immediate impact, or single anomalous event requiring investigation
- Low: minor policy violations or low-confidence behavioral anomalies
