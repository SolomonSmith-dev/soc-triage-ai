---
title: SOC Triage AI
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: RAG-grounded SOC alert triage that refuses without evidence
---

# SOC Triage AI (public demo)

Pick a recorded security alert and get a structured triage: severity, MITRE ATT&CK techniques, recommended actions, escalation decision, and the evidence the answer was grounded in. If retrieval finds nothing relevant, the system refuses and asks for manual review.

Recorded mode: the model step replays the responses Claude (`claude-sonnet-4-5`) gave in the project's 100-case harness run. Observable extraction, retrieval, the refusal guardrail and schema validation run live on every request. This Space has no model key, makes no model calls and costs nothing to run. An edited alert still goes through retrieval and the guardrail; if it reaches the model step, the answer is `not_recorded`.

Requests are rate limited per address and alert text is never logged. Do not paste real alert data.

API: `GET /samples` lists the recorded alerts. `POST /triage` with `{"alert": "..."}` returns the case envelope defined in `packages/contracts`, and the `X-Demo-Replay-Case` header names the recording that answered the model step.

Source: https://github.com/SolomonSmith-dev/soc-triage-ai
