# Phishing Detection Indicators

Phishing remains the top initial access vector. Effective triage requires evaluating sender, content, and target signals together.

## Sender Indicators (MITRE ATT&CK: T1566 Phishing, T1566.002 Spearphishing Link)
- Domain mismatch: display name shows legitimate brand, but envelope sender uses lookalike domain (microsft.com, paypa1.com, anthropic-secure.com)
- Newly registered domains (less than 30 days old)
- Free email services impersonating businesses
- SPF, DKIM, or DMARC failures on domains that should authenticate
- Compromised legitimate accounts sending out of character messages

## Content Indicators (MITRE ATT&CK: T1566.001 Spearphishing Attachment, T1566.002 Spearphishing Link, T1566.003 Spearphishing via Service)
- Urgency manipulation: "your account will be closed in 24 hours", "immediate action required"
- Authority impersonation: claims to be CEO, IT, HR, or external authority
- Generic greetings on supposedly personalized messages
- Hyperlinks where display text differs from actual URL (T1566.002)
- HTML attachments that render fake login pages locally (T1566.001)
- QR codes leading to credential harvesting (quishing)
- Microsoft 365 OAuth consent phishing requesting excessive permissions

## Attachment Indicators
- Office documents with macros (.docm, .xlsm)
- ISO, IMG, VHD files containing LNK or executable content
- Password-protected zip archives (evades scanning)
- Double extensions (invoice.pdf.exe)
- LNK files masquerading as documents
- HTML smuggling: HTML files that assemble malicious payloads in browser

## Target Indicators (raises severity)
- Recipients in Finance, Accounts Payable, or Treasury
- IT administrators with elevated privileges
- Executive assistants with calendar and inbox delegation
- HR personnel during hiring season

## Post-Click Indicators (MITRE ATT&CK: T1566.002 Spearphishing Link, T1078 Valid Accounts, T1204 User Execution)
- Authentication to attacker-controlled domain (T1078 credential compromise)
- Token theft via adversary-in-the-middle (Evilginx, EvilProxy frameworks)
- OAuth grant to suspicious third-party app
- Endpoint contacting known C2 infrastructure

## Severity Classification
- Critical: confirmed credential entry on attacker page, OAuth grant given, or malware execution
- High: user clicked link, authentication attempted, or attachment executed
- Medium: user reported phish before interaction, or suspicious email blocked at gateway after delivery
- Low: phish blocked at gateway, no user exposure

## MITRE Mapping
T1566.001 Spearphishing Attachment, T1566.002 Spearphishing Link, T1566.003 Spearphishing via Service, T1204 User Execution.

Recommended actions: contain user account if credentials may be compromised, hunt for similar messages across the tenant, block sender domain and infrastructure at email gateway and DNS, search for additional victims, review for OAuth grants in M365 audit logs.
