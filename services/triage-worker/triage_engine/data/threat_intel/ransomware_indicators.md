# Ransomware Detection Indicators

Ransomware attacks have evolved into multi-stage operations with reconnaissance, exfiltration, and encryption phases. Modern ransomware operators often spend 7-30 days in the environment before deploying encryption.

## Pre-Encryption Indicators
- Mass enumeration of file shares (SMB scans, share listing)
- Volume Shadow Copy deletion via vssadmin delete shadows or wmic shadowcopy delete
- Backup system access attempts: Veeam, Commvault, Rubrik service account anomalies
- Disabling of security tools: Windows Defender, EDR agents, antivirus services
- Group Policy modifications to disable defenses domain-wide
- RDP enabling on systems where it was previously disabled

## Encryption Phase Indicators
- High volume of file modifications in short time window (thousands of files per minute per host)
- File extension changes to ransomware-specific patterns: .lockbit, .blackcat, .akira, .clop
- Ransom note files appearing in every directory: README.txt, HOW_TO_DECRYPT.txt, DECRYPT_INFO.html
- CPU spikes on file servers and workstations simultaneously
- SMB write activity from unusual sources

## Active Ransomware Families 2024-2025
- LockBit 3.0/Black: most prolific. Uses StealBit for exfiltration. Targets ESXi servers with Linux variant.
- BlackCat/ALPHV: written in Rust. Triple extortion model. Disrupted by FBI February 2024 but resurged.
- Akira: emerged 2023. Hybrid C++/Rust. Targets VPN appliances for initial access.
- Cl0p: known for mass exploitation campaigns including MOVEit and GoAnywhere.
- Play: targets Linux ESXi, uses intermittent encryption for speed.
- Royal: rebrand of Conti members. Uses partial file encryption.

## Severity Classification
- Critical: active encryption detected, ransom notes present, multiple hosts affected
- High: pre-encryption indicators on multiple hosts, backup tampering, defense evasion confirmed
- Medium: single host with suspicious enumeration or shadow copy deletion
- Low: isolated suspicious activity matching ransomware TTP without confirmation

## MITRE Mapping
T1486 Data Encrypted for Impact, T1490 Inhibit System Recovery (shadow copy deletion), T1489 Service Stop (disabling defenses), T1562 Impair Defenses.

Recommended actions for ransomware alerts: immediately isolate affected hosts at the network layer, do not power off (preserves memory forensics), preserve volume shadow copies if any remain, identify patient zero and entry vector, alert legal and executive leadership, engage incident response retainer.
