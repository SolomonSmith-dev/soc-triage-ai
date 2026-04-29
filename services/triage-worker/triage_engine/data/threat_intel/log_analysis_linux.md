# Linux Log Analysis Reference

Linux logging is less standardized than Windows but provides essential visibility into server compromise, lateral movement, and container escape.

## Authentication Logs

### /var/log/auth.log (Debian/Ubuntu) or /var/log/secure (RHEL/CentOS)
Key entries:
- sshd authentication: successful and failed
- sudo invocations
- su transitions
- PAM events
- User account modifications

High-priority patterns:
- Failed SSH from external IPs (brute force)
- Successful SSH from new geographic locations
- Sudo to root by non-admin users
- Authentication using SSH keys not in normal inventory
- Login from accounts with no shell history (suspicious)

### Key SSH indicators
- Multiple authentication failures followed by success (brute force succeeded)
- Login from Tor exit nodes or known malicious IPs
- Unusual SSH client versions in logs
- Reverse SSH tunnel establishment
- SSH key authentication for accounts that should use password+MFA

## System Logs

### /var/log/syslog or /var/log/messages
General system activity. Watch for:
- Cron job modifications and execution
- Service start/stop events
- Kernel messages indicating exploitation (segfaults, OOM kills of security tools)
- USB device insertion in restricted environments

### /var/log/audit/audit.log (auditd)
Detailed kernel audit framework events. Critical rules to monitor:
- execve syscalls for sensitive binaries
- File access on /etc/passwd, /etc/shadow, /etc/sudoers
- Network configuration changes
- Loading of kernel modules
- Setuid program execution

## Container and Cloud Indicators

### Docker
- /var/log/docker.log or journalctl -u docker
- Container escape attempts: privileged containers, host namespace access
- Image pulls from non-corporate registries
- Containers running as root
- Unusual mount points (/var/run/docker.sock mounted into containers)

### Kubernetes
- API server audit logs
- exec into pods (kubectl exec)
- Service account token use from unusual sources
- Privilege escalation via PodSecurityPolicy bypass

## Web Server Logs

### Apache and Nginx Access Logs
Indicators:
- SQL injection patterns: UNION SELECT, OR 1=1, sleep(), benchmark()
- Path traversal: ../../../etc/passwd, %2e%2e%2f
- Command injection: ;, |, &&, dollar-sign-paren, backticks
- Web shell access: shell.php, c99.php, simple-shell.aspx
- Scanner user agents: nikto, sqlmap, nuclei, masscan

## Triage Guidance
For Linux alerts: identify the user account and source IP, check process tree via auditd or osquery, correlate authentication events with subsequent activity, review crontab and systemd timer modifications for persistence. Container alerts require checking the host as well as the container, since escape is the primary concern.

Common attacker behaviors on Linux: install SSH key in authorized_keys, modify /etc/passwd or /etc/shadow, install web shell on web server, deploy crypto miner, establish reverse shell via bash -i or netcat, exfiltrate data via curl or scp.
