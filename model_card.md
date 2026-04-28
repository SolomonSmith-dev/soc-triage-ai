# Model Card: SOC Triage AI

## Intended Use

A Tier 1 SOC analyst assistant for triaging security alerts. Produces structured triage reports with severity classification, MITRE ATT&CK technique mapping, recommended actions, and escalation decisions, all grounded in a curated threat intelligence corpus.

This system is intended to augment, not replace, human analyst judgment. Output is suggestive, not authoritative.

## Out of Scope

- Production SOC deployment without human review
- Automated remediation actions (containment, blocking, account disabling)
- Investigation of advanced persistent threats requiring full incident response
- Compliance, regulatory, or legal determinations

## Limitations and Biases

**Corpus coverage bias**: The threat intelligence corpus reflects publicly known TTPs concentrated in 2023-2024. Novel attack techniques, region-specific threats, and proprietary internal threat intelligence are absent. The system will produce lower-confidence or refused triage for alerts outside this coverage.

**Severity calibration**: The severity framework reflects general SOC operational norms. Organization-specific risk tolerance, asset criticality tiers, and compliance requirements are not incorporated. Production deployment would require corpus customization to match the organization's actual threat model and asset inventory.

**Western-centric threat focus**: The corpus prioritizes adversary groups and TTPs prominent in English-language threat reporting. State-sponsored actors from non-English-speaking regions and threats specific to other geographic regions are underrepresented.

**Embedding model limitations**: all-MiniLM-L6-v2 is a general-purpose model not fine-tuned on security terminology. Specialized terms, novel CVE identifiers, and emerging threat actor names may retrieve poorly until added to the corpus.

**No real-time enrichment**: The system does not query external threat intelligence feeds, IOC databases, or asset management systems. All grounding comes from the static corpus.

**Resolved: phishing technique mapping.** Earlier iterations returned empty MITRE technique lists for phishing alerts despite correct severity classification. Root cause: the corpus chunker separated MITRE technique IDs from the indicator text that scored highest during retrieval, so the model never saw T1566 in context. Fixed by inlining technique references within the indicator sections of the phishing corpus document. Harness now passes 7/7.

## Misuse Risks and Mitigations

**Risk: over-reliance on AI output for high-stakes decisions.**
Mitigation: confidence scores and source attribution surface the system's epistemic state. Guardrail responses explicitly recommend manual review. The model card and README emphasize human-in-the-loop deployment.

**Risk: prompt injection via crafted alert content.**
Mitigation: the prompt template constrains output to a strict JSON schema, and the parser validates schema compliance. Alert content embedded in the prompt cannot escape the structured response format. However, defense in depth would require additional input sanitization in production.

**Risk: false negative on novel attacks.**
Mitigation: the guardrail explicitly refuses rather than fabricates. Out-of-distribution alerts produce informational severity with manual review recommendation, not a false-confident benign verdict.

**Risk: false positive escalation flooding analyst queue.**
Mitigation: severity calibration favors conservative classification. The harness includes test cases for both alert types and benign content to detect over-escalation drift.

## Testing Surprises

The most instructive harness result was the Log4Shell case. The alert specified the target system was patched, but the model classified it as high severity with escalation recommended. Initial test design expected medium-or-low severity to acknowledge the patch. On reflection, the test expectation was wrong: an alert claiming patched status should not fully suppress severity, because the alert text itself is unverified. Real SOC practice treats self-reported patching claims as untrusted until confirmed. The system's conservative behavior matches this practice. The test was updated to accept the broader severity range.

The retrieval similarity scores varied widely across test cases (0.247 to 0.541) with no clear correlation to triage accuracy. The credential dumping test had a moderate retrieval score (0.488) and produced excellent triage. The gibberish test had the lowest score (0.247) and correctly triggered guardrail behavior. This indicates that retrieval quality and triage accuracy are partially independent, and that confidence scoring should incorporate signals beyond similarity alone in future iterations.

The reliability iteration cycle was itself instructive. The initial harness run produced 3/7 pass rate due to inconsistent MITRE technique mapping. Strengthening the prompt with explicit instructions to require techniques for non-informational severity improved pass rate to 6/7. An attempted retry mechanism to catch the remaining failure case introduced additional failure modes (numeric confidence values, missing required fields, unpredictable LLM output drift on retry) that reduced overall system reliability. The retry was reverted. The final fix was a corpus-level change: the phishing document's MITRE technique IDs lived in a separate chunk that the retriever never surfaced alongside the indicator sections the model actually used. Inlining the technique references into those sections brought the harness to 7/7 (100%). The lesson: when a RAG system produces incomplete output, trace backward from the LLM through retrieval to the corpus structure before adding prompt complexity.

## AI Collaboration During Development

I used Claude Sonnet 4.5 as a development partner throughout this project.

**Helpful suggestion**: When the initial harness run produced 3/7 pass rate, the model identified that the prompt allowed the LLM to skip MITRE technique mapping on alerts where severity classification was clear. The proposed fix added explicit prompt instruction requiring techniques for non-informational severity. After applying this fix, pass rate improved from 43% to 86%. This was directly responsible for the system reaching production-quality reliability for the project deliverable.

**Flawed suggestion**: Early in the build, Claude suggested using ChromaDB as the vector store. For a corpus of approximately 100 chunks this added meaningful infrastructure overhead (additional dependency, persistent storage configuration, lifecycle management) for no measurable retrieval quality benefit. I switched to numpy cosine similarity, which executed retrieval in single-digit milliseconds and made the entire system simpler to set up and explain. The lesson: AI suggestions optimize for canonical patterns in training data, not for the specific scale and constraints of a project. Right-sizing infrastructure to actual needs requires human judgment.

A second flawed suggestion came later: when 6/7 pass rate emerged, Claude proposed adding a retry mechanism to catch the remaining failure. The retry implementation introduced new failure modes that reduced overall system stability. The fix was to revert and diagnose the actual root cause: the corpus chunking strategy separated MITRE technique IDs from the indicator text the retriever was surfacing. Inlining the technique references into the relevant corpus sections was the correct fix. The deeper lesson: when a RAG pipeline produces incomplete output, the root cause is usually in the data or retrieval layer, not the prompt. Adding complexity (retries, post-processing) to work around a data-level problem produces net regressions.

## Evaluation Methodology

The reliability harness consists of 7 test cases drawn from realistic SOC alert categories:

- Phishing with credential entry
- Active ransomware (multi-host)
- Credential dumping (LSASS via comsvcs.dll)
- Brute force from Tor exit
- Exploitation attempt against claimed-patched system
- Out-of-scope gibberish (guardrail validation)
- Insider threat with departing employee profile

Each case defines expected severity range, expected MITRE techniques, expected escalation, and minimum retrieval similarity. Pass criteria require all checks to succeed. The harness produces a JSON results dump and printed pass/fail summary.

This methodology validates classification accuracy and guardrail behavior but does not measure latency under load, cost per triage, or robustness against adversarial inputs. Production deployment would require expanding the harness to several hundred cases with regular regression runs and adversarial test sets.

## Productization Addendum (v1.1)

After the harness reached 7/7, the system was extended into a portfolio-grade MVP without modifying the core LLM pipeline. The following layers were added around it; the prompt, retriever, corpus, and harness remain unchanged.

**Deterministic observable extraction.** Before the LLM call, raw alert text passes through a regex-only extractor (`extractors.py`) that pulls 12 observable types: IPv4, email, URL, domain, MD5/SHA1/SHA256 hashes, registry path, process, filename, hostname, and username. No NLP, no API calls, no model dependency. Process names are filtered out of domain candidates and usernames are stripped of trailing punctuation, both validated by regression tests. This layer exists for analyst feedback (visible immediately, before the ~8s LLM call returns) and as a structured input for downstream tooling. Failure mode is well-defined: regex misses are silent, never hallucinated.

**Case envelope and uncertainty modes.** The triage result, observables, retrieval hits, and a guardrail flag are composed into a single deterministic case envelope (`case_package.py`) keyed by `SOC-YYYYMMDD-XXXX`. The envelope additionally derives an *uncertainty mode* — `actionable`, `needs_more_context`, `insufficient_evidence`, or `out_of_scope` — from confidence and average retrieval score, evaluated in priority order. This is a deterministic post-processing classification, **not** a prompt change: the LLM pipeline produces the same output it always did, and the uncertainty mode is computed in Python afterward. The intent is to give analysts a calibrated signal about when to trust the output without retraining or re-prompting.

**Evidence traceability.** Every chunk retrieved during triage is recorded in the case envelope with its similarity score and a `cited` boolean indicating whether its source document was actually attributed in the LLM's `sources` field. This exposes the gap between *retrieved* and *used* evidence — a useful reviewer signal. A chunk above the similarity threshold but uncited may indicate the LLM drew on different context than the retriever surfaced as primary, which is a calibration signal worth noting.

**Analyst override logging.** The Streamlit UI lets an analyst override severity or escalation with a written rationale. Overrides are stored as structured records in the case envelope alongside the original LLM output — never replacing it. This preserves the model's actual prediction for downstream evaluation while allowing operational corrections, and it makes the audit trail explicit when the human and the model disagree.

**Evaluation surfacing.** The reliability harness, previously CLI-only, is now exposed in the Streamlit UI with both a static load (last saved results) and an on-demand live re-run (7 API calls). Per-case results, severity / escalation accuracy, average retrieval, and average latency are computed by `evaluation.py` from the same `evaluate_case` logic the CLI harness uses — no duplication.

**What this addendum does *not* claim.** None of these additions improve the underlying triage decisions. The LLM pipeline produces identical output. The added layers are about *visibility*, *traceability*, *calibration*, and *operational ergonomics* — turning a working triage function into a tool an analyst could plausibly use. Genuinely improving classification quality would require corpus expansion, fine-tuning, or model-level changes, none of which are in scope here.
