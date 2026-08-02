# Network Anomaly Detection Patterns

Network telemetry provides high-fidelity signals for detecting adversary activity that endpoint controls miss.

## C2 Beaconing
Adversaries maintain command and control channels via periodic check-ins. Detection focuses on temporal regularity and traffic shape.
- Consistent interval connections: every 60 seconds, every 5 minutes, jittered around base interval
- Small request sizes with consistent response sizes
- Connections to rare destinations (low prevalence in environment)
- HTTPS connections with self-signed or unusual certificates
- DNS queries with high entropy subdomains (DGA-generated)
- Common C2 frameworks: Cobalt Strike, Sliver, Mythic, Brute Ratel, Metasploit

Beaconing detection indicators: connection count anomaly, periodicity score above threshold, entropy of inter-arrival times below threshold.

## DNS Tunneling
Data exfiltration or C2 over DNS. Indicators include unusually long DNS query names, high query volume to single domain, TXT record queries to unusual domains, and queries with base64 or hex-encoded subdomains.

## Port Scanning
- Horizontal scan: many hosts on single port (looking for vulnerable service)
- Vertical scan: many ports on single host (mapping target)
- Internal scanning from compromised host indicates lateral movement reconnaissance

Indicators: connection attempt rate above baseline, high failed connection ratio, sequential or patterned destination addresses or ports.

## Data Exfiltration Patterns
- Large outbound transfers during off-hours
- Outbound connections to cloud storage (Mega, Dropbox, Google Drive) from servers that should not use them
- Use of legitimate file transfer services to evade DLP: WeTransfer, transfer.sh, anonfiles
- Compressed and encrypted archive uploads
- Slow-rate exfiltration (low and slow) to evade volume thresholds

## Tor and Anonymization
- Connections to known Tor exit nodes
- Use of bridges and pluggable transports (obfs4)
- VPN to consumer-grade services from corporate hosts

## Suspicious User Agents
- Curl, wget, python-requests from user workstations
- PowerShell user agent strings
- Empty or generic user agents
- User agents matching known malware families

## MITRE Mapping
T1071 Application Layer Protocol (C2), T1572 Protocol Tunneling, T1046 Network Service Discovery (scanning), T1048 Exfiltration Over Alternative Protocol, T1090 Proxy.

## Triage Guidance
Network anomaly alerts require correlation with endpoint telemetry. A beaconing alert without process attribution has limited actionability. Recommended actions: identify source endpoint and process, check destination reputation in threat intelligence, review authentication and execution events around alert time, isolate source if confirmed malicious.
