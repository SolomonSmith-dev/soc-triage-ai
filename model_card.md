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

**Inconsistent technique mapping on phishing alerts**: The reliability harness revealed that the model occasionally produces empty MITRE technique lists despite explicit prompt instruction to populate them for non-informational severity. Pass rate for technique-mapping validation is 6/7 cases. The phishing test case consistently surfaces this limitation.

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

The reliability iteration cycle was itself instructive. The initial harness run produced 3/7 pass rate due to inconsistent MITRE technique mapping. Strengthening the prompt with explicit instructions to require techniques for non-informational severity improved pass rate to 6/7. An attempted retry mechanism to catch the remaining failure case introduced additional failure modes (numeric confidence values, missing required fields, unpredictable LLM output drift on retry) that reduced overall system reliability. The retry was reverted in favor of the simpler 6/7 version. The lesson: chasing the last few percent of reliability through prompt engineering and validation logic has diminishing returns. Robust schema enforcement requires structured output mechanisms (tool calling, response_format constraints) that are beyond this project's scope.

## AI Collaboration During Development

I used Claude Sonnet 4.5 as a development partner throughout this project.

**Helpful suggestion**: When the initial harness run produced 3/7 pass rate, the model identified that the prompt allowed the LLM to skip MITRE technique mapping on alerts where severity classification was clear. The proposed fix added explicit prompt instruction requiring techniques for non-informational severity. After applying this fix, pass rate improved from 43% to 86%. This was directly responsible for the system reaching production-quality reliability for the project deliverable.

**Flawed suggestion**: Early in the build, Claude suggested using ChromaDB as the vector store. For a corpus of approximately 100 chunks this added meaningful infrastructure overhead (additional dependency, persistent storage configuration, lifecycle management) for no measurable retrieval quality benefit. I switched to numpy cosine similarity, which executed retrieval in single-digit milliseconds and made the entire system simpler to set up and explain. The lesson: AI suggestions optimize for canonical patterns in training data, not for the specific scale and constraints of a project. Right-sizing infrastructure to actual needs requires human judgment.

A second flawed suggestion came later: when 6/7 pass rate emerged, Claude proposed adding a retry mechanism to catch the remaining failure. The retry implementation introduced new failure modes that reduced overall system stability. The fix was to revert and accept 6/7 as a stable plateau. The deeper lesson: complexity added in pursuit of marginal reliability gains often produces net regressions, especially when the underlying mechanism (in this case, free-form LLM output) doesn't support strong reliability guarantees.

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
