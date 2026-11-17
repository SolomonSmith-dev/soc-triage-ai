---
title: SOC Triage AI
colorFrom: blue
colorTo: gray
sdk: gradio
sdk_version: 6.32.0
python_version: 3.12.12
app_file: app.py
pinned: false
license: mit
short_description: RAG-grounded SOC alert triage that refuses without evidence
preload_from_hub:
  - sentence-transformers/all-MiniLM-L6-v2
---

# SOC Triage AI (public demo)

Pick a security alert and get a structured triage: severity, MITRE ATT&CK techniques, recommended actions, escalation decision, and the evidence the answer was grounded in. If retrieval finds nothing relevant, the system refuses and asks for manual review.

The Space runs in recorded mode unless its owner switches it to live mode; the page header and the `X-Demo-Mode` response header say which. Recorded mode: the model step replays the responses Claude (`claude-sonnet-4-5`) gave in the project's 100-case harness run, so it needs no model key, makes no model calls and costs nothing. Observable extraction, retrieval, the refusal guardrail and schema validation run live on every request. An edited alert still goes through retrieval and the guardrail; if it reaches the model step, the answer is `not_recorded`. Live mode calls Claude for each request that passes the guards, under a daily token cap.

The Space is on ZeroGPU hardware because that is where Hugging Face hosts free Gradio Spaces. No request uses a GPU: the embedding model runs on the CPU. ZeroGPU only starts a Space that has a `@spaces.GPU` event handler, so the page carries one no-op handler behind a hidden control.

Requests are rate limited per address and alert text is never logged. Do not paste real alert data.

API: `GET /samples` lists the alerts to try. `POST /triage` with `{"alert": "..."}` returns the case envelope defined in `packages/contracts`. In recorded mode the `X-Demo-Replay-Case` header names the recording that answered the model step.

Source: https://github.com/SolomonSmith-dev/soc-triage-ai
