"""SOC Triage AI: RAG-grounded structured triage of security alerts.

Conceptually inspired by The Mood Machine (CodePath AI110 Module 3), which
classified text into sentiment categories using prompt-engineered LLM calls.
SOC Triage AI applies the same core pattern (LLM-based categorical classification
with structured output) to a higher-stakes domain. The implementation is largely
new: retrieval-augmented grounding, MITRE ATT&CK mapping, schema validation, and
a reliability harness are additions specific to the security domain.
"""
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, Any

from anthropic import Anthropic
from dotenv import load_dotenv

from triage_engine.rag.corpus import load_corpus
from triage_engine.rag.retriever import ThreatIntelRetriever

CORPUS_DIR = str(Path(__file__).parent / "data" / "threat_intel")

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 1024

TRIAGE_PROMPT = """You are a Tier 1 SOC analyst assistant performing alert triage.

Use ONLY the threat intelligence context below. Do not invent CVE numbers, MITRE technique IDs, or threat actor names.

REQUIRED BEHAVIOR FOR MITRE TECHNIQUES:
- For any alert with severity higher than "informational", you MUST identify at least one MITRE ATT&CK technique from the threat intelligence context.
- Format technique IDs as "T1234" or "T1234.001" (with sub-technique when applicable).
- If multiple techniques apply, list all that are clearly supported by the context.
- Only return an empty mitre_techniques list when severity is "informational".

If the alert appears benign or out of scope (gibberish, unrelated content), set severity to "informational" and escalate to false.

THREAT INTELLIGENCE CONTEXT:
{context}

SECURITY ALERT:
{alert}

Respond with ONLY valid JSON matching this exact schema. No markdown fences, no preamble:
{{
  "severity": "critical" | "high" | "medium" | "low" | "informational",
  "confidence": "high" | "medium" | "low",
  "mitre_techniques": ["T1234", "T5678.001"],
  "summary": "one-sentence analyst-facing summary",
  "recommended_actions": ["action 1", "action 2", "action 3"],
  "escalate": true | false,
  "reasoning": "2-3 sentence explanation grounded in context"
}}"""


class SOCTriage:
    """Main triage pipeline. RAG retrieval + structured LLM output + guardrails."""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Add to .env or export in shell."
            )
        self.client = Anthropic(api_key=api_key)
        self.retriever = ThreatIntelRetriever()
        self.retriever.index(load_corpus(CORPUS_DIR))

    def triage(self, alert: str) -> Dict[str, Any]:
        """Triage a security alert. Returns structured JSON dict."""
        result, _, _ = self._run_triage(alert)
        return result

    def triage_with_context(
        self, alert: str
    ) -> tuple[Dict[str, Any], list, bool]:
        """Like triage() but also returns retrieval hits and guardrail flag.

        Used by case_package.py to build full case envelopes. The existing
        triage() return signature is preserved for the reliability harness.
        """
        return self._run_triage(alert)

    def _run_triage(
        self, alert: str
    ) -> tuple[Dict[str, Any], list, bool]:
        """Shared core. Returns (result_dict, retrieval_hits, guardrail_triggered)."""
        if not alert or not alert.strip():
            return (
                self._guardrail_response(
                    "Empty alert input", retrieval_score=0.0, sources=[]
                ),
                [],
                True,
            )

        hits = self.retriever.retrieve(alert, top_k=4)

        if not hits:
            logger.warning(f"No corpus matches for alert: {alert[:100]}")
            return (
                self._guardrail_response(
                    "No matching threat intelligence found. Manual review required.",
                    retrieval_score=0.0,
                    sources=[],
                ),
                [],
                True,
            )

        context = "\n\n".join(
            f"[Source: {chunk['source']} | Similarity: {score:.2f}]\n{chunk['text']}"
            for chunk, score in hits
        )
        avg_score = sum(s for _, s in hits) / len(hits)
        sources = list({chunk["source"] for chunk, _ in hits})

        prompt = TRIAGE_PROMPT.format(context=context, alert=alert)

        raw = ""
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            parsed = self._parse_json(raw)
            self._validate_schema(parsed)
            parsed["sources"] = sources
            parsed["retrieval_score"] = round(avg_score, 3)
            return parsed, hits, False

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}. Raw: {raw[:300]}")
            return (
                self._guardrail_response(
                    "LLM produced malformed JSON",
                    retrieval_score=avg_score,
                    sources=sources,
                ),
                hits,
                True,
            )
        except Exception as e:
            logger.error(f"Triage failed: {type(e).__name__}: {e}")
            return (
                self._guardrail_response(
                    f"System error: {type(e).__name__}",
                    retrieval_score=avg_score,
                    sources=sources,
                ),
                hits,
                True,
            )

    def _parse_json(self, raw: str) -> Dict:
        """Extract JSON object from LLM response, handling stray markdown."""
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise json.JSONDecodeError("No JSON object found", cleaned, 0)
        return json.loads(match.group())

    def _validate_schema(self, parsed: Dict) -> None:
        """Verify required fields are present with correct types and values."""
        required = {
            "severity": str,
            "confidence": str,
            "mitre_techniques": list,
            "summary": str,
            "recommended_actions": list,
            "escalate": bool,
            "reasoning": str,
        }
        for field, expected_type in required.items():
            if field not in parsed:
                raise ValueError(f"Missing required field: {field}")
            if not isinstance(parsed[field], expected_type):
                raise ValueError(
                    f"Field {field} has wrong type. "
                    f"Expected {expected_type.__name__}, got {type(parsed[field]).__name__}"
                )
        valid_severities = {"critical", "high", "medium", "low", "informational"}
        if parsed["severity"] not in valid_severities:
            raise ValueError(f"Invalid severity: {parsed['severity']}")
        valid_confidence = {"high", "medium", "low"}
        if parsed["confidence"] not in valid_confidence:
            raise ValueError(f"Invalid confidence: {parsed['confidence']}")

    def _guardrail_response(
        self, reason: str, retrieval_score: float, sources: list
    ) -> Dict:
        """Safe fallback when retrieval fails or LLM output is invalid."""
        return {
            "severity": "informational",
            "confidence": "low",
            "mitre_techniques": [],
            "summary": reason,
            "recommended_actions": ["Manual analyst review required"],
            "escalate": False,
            "reasoning": (
                f"Guardrail triggered: {reason}. "
                f"System refused to fabricate triage without grounding."
            ),
            "sources": sources,
            "retrieval_score": round(retrieval_score, 3),
        }


def format_report(result: Dict) -> str:
    """Pretty-print triage result for CLI display."""
    severity = result["severity"].upper()
    conf = result["confidence"].upper()
    lines = [
        "=" * 70,
        "SOC TRIAGE REPORT",
        "=" * 70,
        f"Severity:        {severity}",
        f"Confidence:      {conf}",
        f"Escalate:        {result['escalate']}",
        f"Retrieval Score: {result.get('retrieval_score', 'n/a')}",
        "",
        f"Summary:         {result['summary']}",
        "",
        f"MITRE Techniques: {', '.join(result['mitre_techniques']) or 'None'}",
        "",
        "Recommended Actions:",
    ]
    for i, action in enumerate(result["recommended_actions"], 1):
        lines.append(f"  {i}. {action}")
    lines.extend([
        "",
        f"Reasoning: {result['reasoning']}",
        "",
        f"Sources: {', '.join(result.get('sources', [])) or 'None'}",
        "=" * 70,
    ])
    return "\n".join(lines)


def main():
    """CLI entry point. Usage: python triage.py 'alert text here'"""
    if len(sys.argv) < 2:
        print("Usage: python triage.py '<alert text>'")
        print("\nExample:")
        print("  python triage.py 'PowerShell encoded command from outlook.exe'")
        sys.exit(1)

    alert = " ".join(sys.argv[1:])
    triage = SOCTriage()
    result = triage.triage(alert)
    print(format_report(result))
    print("\nFull JSON:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
