---
title: SOC Triage AI
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: RAG-grounded SOC alert triage that refuses when it has no evidence
---

# SOC Triage AI (public demo)

Paste a security alert, get a structured triage: severity, MITRE ATT&CK techniques, recommended actions, escalation decision, and the evidence the answer was grounded in. If retrieval finds nothing relevant, the system refuses and asks for manual review.

Public demo limits: requests are rate limited per address, total model usage is capped per day, and alert text is never logged. Do not paste real alert data.

API: `POST /triage` with `{"alert": "..."}` returns the case envelope defined in `packages/contracts`.

Source: https://github.com/SolomonSmith-dev/soc-triage-ai
