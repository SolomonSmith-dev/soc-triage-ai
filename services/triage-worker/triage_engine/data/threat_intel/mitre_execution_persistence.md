# MITRE ATT&CK: Execution and Persistence

## T1059 Command and Scripting Interpreter
The most common execution technique. Adversaries abuse legitimate interpreters to run code.
- T1059.001 PowerShell: encoded commands, downloaded scripts, AMSI bypass attempts
- T1059.003 Windows Command Shell: cmd.exe spawning unusual children, batch script execution from temp directories
- T1059.004 Unix Shell: bash or sh executing curl/wget piped to interpreter
- T1059.006 Python: malicious python scripts often delivered via supply chain compromise

Indicators include long base64-encoded command lines, parent-child process anomalies (Word spawning PowerShell), and outbound connections initiated by interpreters. Severity is high when combined with network egress.

## T1204 User Execution
Adversary requires user to execute malicious file. Often paired with T1566 phishing. Sub-techniques include T1204.001 malicious link and T1204.002 malicious file.

Indicators: user clicks email link, then process tree shows browser spawning office app spawning script interpreter. This pattern alone is high-confidence malicious.

## T1547 Boot or Logon Autostart Execution
Persistence via autostart locations. Most common sub-techniques:
- T1547.001 Registry Run Keys: HKCU\Software\Microsoft\Windows\CurrentVersion\Run modifications
- T1547.009 Shortcut Modification: malicious LNK files in Startup folder

## T1053 Scheduled Task/Job
- T1053.005 Scheduled Task: schtasks.exe creating tasks with SYSTEM privileges
- T1053.003 Cron: unauthorized cron entries on Linux systems

Indicators include task creation by non-admin accounts, tasks pointing to scripts in %TEMP% or %APPDATA%, and tasks with hidden flags.

## T1543 Create or Modify System Process
- T1543.003 Windows Service: sc.exe or PowerShell creating services pointing to suspicious binaries
- T1543.001 Launch Daemon (macOS): plist files in /Library/LaunchDaemons

Triage priority for execution and persistence alerts: identify the parent process, determine if the executed code performed network egress or credential access, and check for additional persistence mechanisms which often indicate sophisticated actors.
