# SOC Alert Severity Classification Framework

Consistent severity assignment is critical for SOC operations. This framework provides decision criteria for severity levels and escalation thresholds.

## Severity Levels

### Critical
Immediate response required. Page on-call analyst.
- Confirmed active intrusion: encryption in progress, active C2 channel, ongoing data exfiltration
- Domain admin or root compromise on production systems
- Internet-exposed system actively being exploited
- Ransomware indicators on multiple hosts
- Confirmed data breach involving regulated data (PII, PHI, PCI, classified)
- Compromise of authentication infrastructure (AD, IdP, MFA provider)

Response time: immediate, less than 15 minutes to containment action.

### High
Urgent investigation required. Same shift response.
- Successful exploitation of known vulnerability
- Confirmed credential compromise of privileged user
- Malware execution confirmed on endpoint
- Lateral movement detected
- Pre-encryption ransomware indicators
- Successful phishing with credential entry

Response time: within 1 hour to triage decision, within 4 hours to containment.

### Medium
Investigation required, not blocking.
- Suspicious activity matching known TTPs without confirmation
- Failed exploitation attempts against unpatched systems
- Anomalous behavior from non-privileged user
- Suspicious file detected and quarantined by endpoint protection
- User reported phishing before interaction
- Out-of-baseline activity requiring context

Response time: within current shift, within 24 hours.

### Low
Triage and document. Action only if pattern emerges.
- Blocked attacks at perimeter
- Policy violations without security impact
- Informational alerts during business operations
- Single-source low-volume scanning from internet
- Failed authentication within normal noise floor

Response time: within 5 business days.

### Informational
Logged for context, no investigation required unless correlated with other events.

## Decision Factors

### Asset Criticality
Multiplier applied to base severity:
- Tier 0: domain controllers, identity providers, certificate authorities, backup systems
- Tier 1: production application servers, database servers with sensitive data
- Tier 2: standard production servers, executive workstations
- Tier 3: standard user workstations, development systems
- Tier 4: test and isolated systems

A medium-severity alert on a Tier 0 system becomes high or critical.

### Confidence Level
- High confidence: multiple corroborating indicators, known signature match, behavioral anomaly with clear malicious intent
- Medium confidence: single strong indicator or multiple weak indicators
- Low confidence: weak signal, possible false positive, requires context

Low confidence reduces severity by one level unless asset criticality compensates.

### Scope
- Single host vs. multiple hosts
- Single user vs. multiple users
- Contained subnet vs. crossing security boundaries
- Internal only vs. internet-facing component

Multi-host or boundary-crossing scope raises severity.

## Escalation Triggers

Always escalate to incident response leadership when:
- Critical severity confirmed
- Multiple high-severity alerts within short timeframe (possible coordinated attack)
- Evidence of insider threat involving privileged user
- Indicators of nation-state TTPs
- Regulatory or legal implications likely
- Public attention possible (breach disclosure, leaked data)

## Triage Quality Standards
Every alert triage should produce: severity assignment with justification, recommended immediate actions, indicators of compromise extracted, related alerts identified, and escalation decision documented. Inconsistent severity assignment is the single largest source of SOC inefficiency.
