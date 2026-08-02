# Critical CVEs: 2023-2024 High-Impact Vulnerabilities

## CVE-2023-4966 Citrix Bleed
NetScaler ADC and Gateway sensitive information disclosure. Allows session token theft enabling MFA bypass. Exploited by LockBit, Medusa, and other ransomware affiliates. Indicators: unusual session hijacks, authentication from impossible geographic locations, post-auth activity without corresponding login event.

## CVE-2023-34362 MOVEit Transfer SQL Injection
Critical SQL injection in Progress MOVEit Transfer. Mass exploited by Cl0p ransomware affiliate Lace Tempest in May-June 2023. Affected over 2,500 organizations. Indicators: human2.aspx web shell, unusual queries against MOVEit database, large outbound transfers from MOVEit servers.

## CVE-2023-22515 Confluence Broken Access Control
Atlassian Confluence Data Center and Server. Allows creation of administrator accounts without authentication. Exploited by Storm-0062 (China-nexus). Indicators: new admin user creation, unusual REST API calls to /setup endpoints.

## CVE-2024-3094 XZ Utils Backdoor
Supply chain backdoor in liblzma library affecting xz versions 5.6.0 and 5.6.1. Discovered before widespread deployment. Backdoor enabled remote code execution via SSH on affected systems. Indicators: presence of vulnerable xz version, unusual sshd memory patterns.

## CVE-2024-21887 Ivanti Connect Secure Command Injection
Ivanti VPN appliance command injection chained with CVE-2023-46805 authentication bypass. Mass exploited January 2024. Indicators: web shell deployment, KrustyLoader malware, configuration file exfiltration.

## CVE-2024-3400 Palo Alto GlobalProtect
Command injection in PAN-OS GlobalProtect feature. Exploited as zero-day by UTA0218. Indicators: unusual GlobalProtect logs, files in /var/log/pan/, outbound connections from firewall management plane.

## Log4Shell Family
- CVE-2021-44228 Log4j RCE: still actively exploited in 2024 against unpatched systems
- CVE-2021-45046, CVE-2021-45105: follow-up Log4j vulnerabilities
Indicators: JNDI strings in logs (jndi:ldap, jndi:rmi), outbound LDAP/RMI from Java applications, child processes spawned by Java services.

## CVE-2024-23897 Jenkins
Arbitrary file read via CLI. Can lead to RCE via cryptographic key disclosure. Indicators: unusual Jenkins CLI activity, file reads of secrets.key.

## Triage Guidance
When an alert references a CVE, check: is the affected system internet-exposed, is it patched, is there evidence of exploitation (web shells, unusual processes, outbound connections), and is the vulnerability being actively exploited in the wild. CISA KEV catalog membership raises severity to critical.

## MITRE Mapping
T1190 Exploit Public-Facing Application is the primary technique for all CVE exploitation alerts.
