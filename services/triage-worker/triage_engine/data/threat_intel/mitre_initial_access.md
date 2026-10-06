# MITRE ATT&CK: Initial Access

Initial access techniques represent how adversaries gain their first foothold in a target environment. These are the entry points that SOC analysts must triage with high priority because they precede all subsequent attack stages.

## T1566 Phishing
Adversaries send malicious emails to gain access. Three sub-techniques are most common:
- T1566.001 Spearphishing Attachment: malicious file (often Office macro, ISO, LNK, or PDF) delivered as email attachment
- T1566.002 Spearphishing Link: malicious URL leads to credential harvesting page or drive-by download
- T1566.003 Spearphishing via Service: abuse of legitimate services like LinkedIn or Discord to bypass email filters

Indicators include sender domain mismatch, urgency language, attachments with double extensions, and links to recently registered domains. Severity is typically high when the recipient is in finance, executive, or IT roles.

## T1190 Exploit Public-Facing Application
Adversaries exploit vulnerabilities in internet-facing services like web servers, VPN appliances, or email gateways. Recent campaigns have exploited Citrix Bleed (CVE-2023-4966), MOVEit Transfer (CVE-2023-34362), and Confluence (CVE-2023-22515).

Indicators include unusual outbound traffic from web servers, new processes spawned by web server accounts, and authentication anomalies on appliances. Severity is critical when the vulnerable system is internet-exposed and unpatched.

## T1078 Valid Accounts
Adversaries use legitimate credentials obtained through phishing, infostealer logs, or password spray. Hardest to detect because there is no malware signature.

Indicators include impossible travel, login from new geography, off-hours access, and use of legacy authentication protocols. Recommended action is to disable the account, revoke active sessions, and force password reset with MFA enrollment.

## T1133 External Remote Services
Adversaries leverage exposed RDP, SSH, VPN, or remote management tools. Often paired with T1078 once credentials are obtained.

Triage priority for initial access alerts: confirm the account or service involved, determine if MFA was bypassed, identify any post-exploitation activity, and isolate the affected system if execution stage indicators are present.
