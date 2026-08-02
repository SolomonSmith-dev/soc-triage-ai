# MITRE ATT&CK: Credential Access and Lateral Movement

## T1003 OS Credential Dumping
- T1003.001 LSASS Memory: tools like Mimikatz, Pypykatz, or comsvcs.dll abuse to dump LSASS process memory
- T1003.002 Security Account Manager: SAM hive extraction via reg save or vssadmin
- T1003.003 NTDS: ntds.dit extraction on domain controllers, often paired with DCSync attacks

Indicators include suspicious access to LSASS handle, unusual processes reading SAM registry hive, and volume shadow copy creation followed by file extraction. Severity is critical because compromised credentials enable broad lateral movement.

## T1110 Brute Force
- T1110.001 Password Guessing: low-volume targeted attempts
- T1110.003 Password Spraying: single password against many accounts to evade lockout
- T1110.004 Credential Stuffing: known credential pairs from breach dumps

Indicators include high failed authentication count, authentication attempts across many accounts from single source IP, and successful login immediately following failures.

## T1555 Credentials from Password Stores
Adversaries extract credentials from browsers, password managers, or keychain stores. Infostealer malware like Redline, Raccoon, and Lumma specialize in this.

## T1021 Remote Services (Lateral Movement)
- T1021.001 RDP: lateral RDP from non-admin workstations is highly suspicious
- T1021.002 SMB/Windows Admin Shares: psexec, smbexec, wmiexec patterns
- T1021.006 WinRM: powershell remoting abuse

Indicators include authentication chains across multiple hosts in short time windows, use of admin shares (C$, ADMIN$), and remote process creation.

## T1570 Lateral Tool Transfer
Adversaries copy tools to additional systems. Indicators include SMB file writes to admin shares, use of certutil for transfer, and dropped binaries in C:\Windows\Temp or \\target\C$\.

Triage priority for credential access and lateral movement: contain the affected account immediately, identify all systems where the credential was used, force domain-wide credential rotation if domain admin is compromised, and review for golden ticket or silver ticket indicators.
