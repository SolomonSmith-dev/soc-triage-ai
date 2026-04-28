# Windows Log Analysis Reference

Windows event logs are foundational to SOC detection. Knowing the high-value event IDs and their interpretation is essential for alert triage.

## Authentication Events (Security Log)

### Event ID 4624 Successful Logon
Logon Type field is critical for triage:
- Type 2 Interactive: console or local logon
- Type 3 Network: SMB, file share access (most common, often noisy)
- Type 4 Batch: scheduled task execution
- Type 5 Service: service account
- Type 7 Unlock: workstation unlock
- Type 8 NetworkCleartext: cleartext credentials sent (high suspicion)
- Type 9 NewCredentials: RunAs with explicit credentials
- Type 10 RemoteInteractive: RDP
- Type 11 CachedInteractive: cached credentials (offline domain join)

High-priority patterns: Type 10 from non-admin workstations, Type 9 followed by network logons (pass-the-hash indicator), Type 3 with NTLM where Kerberos was expected.

### Event ID 4625 Failed Logon
Failure Reason codes indicate attack type:
- 0xC000006A: bad password (brute force)
- 0xC0000064: bad username (account enumeration)
- 0xC0000234: account locked
- 0xC0000071: expired password
- 0xC000018C: trust relationship failure

High-volume 4625 events from single source indicate password spray. High-volume across many sources to single account indicates targeted attack.

### Event ID 4672 Special Privileges Assigned
Logged when privileged group membership is invoked. Useful for tracking admin activity and detecting privilege abuse.

### Event ID 4720, 4722, 4724, 4725, 4726, 4738
Account management events: creation, enabling, password reset, disabling, deletion, modification. Critical for detecting unauthorized account creation by adversaries establishing persistence.

### Event ID 4768, 4769, 4771
Kerberos events:
- 4768 TGT request: shows initial authentication
- 4769 TGS request: shows resource access (service ticket)
- 4771 Pre-authentication failed: useful for AS-REP roasting detection

Kerberoasting indicator: 4769 events for service accounts with weak encryption type (RC4) followed by ticket cracking attempts.

## Process Events

### Event ID 4688 Process Creation
Requires audit policy enablement and ideally command line logging.
High-priority patterns:
- powershell.exe with -enc, -encodedcommand, or hidden window flag
- cmd.exe spawned by Office applications
- whoami, net.exe, nltest.exe (recon commands)
- rundll32.exe with unusual DLL paths
- mshta.exe execution
- Living-off-the-land binaries (LOLBins): certutil, bitsadmin, regsvr32, msiexec

### Event ID 4697 Service Installation
Service creation events reveal persistence and lateral movement (PsExec creates services).

## Sysmon Events (Requires Deployment)

Sysmon provides richer telemetry than native Windows logs:
- Event ID 1: Process creation with hash and parent
- Event ID 3: Network connection
- Event ID 7: Image loaded (DLL hijacking detection)
- Event ID 11: File creation
- Event ID 13: Registry value set
- Event ID 22: DNS query

## Triage Guidance
For Windows alerts, always check the parent process, command line, user context, and source workstation. Correlate authentication events with process creation events using the logon ID field. Pivot from suspicious processes to network events to identify C2 or data exfiltration.
