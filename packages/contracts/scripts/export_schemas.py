"""Export Pydantic models as JSON Schema for cross-language consumption."""
import json
from pathlib import Path

from soc_contracts import (
    AlertIngestRequest,
    AlertIngestResponse,
    CaseEnvelope,
    CaseSummary,
    CorpusVersion,
    EvalRunSummary,
    OverrideRequest,
    RetrievalDebugResponse,
    TriageJobRequest,
    TriageJobResponse,
)

OUT = Path(__file__).resolve().parent.parent / "dist" / "schemas"
OUT.mkdir(parents=True, exist_ok=True)

models = [
    AlertIngestRequest,
    AlertIngestResponse,
    CaseEnvelope,
    CaseSummary,
    CorpusVersion,
    EvalRunSummary,
    OverrideRequest,
    RetrievalDebugResponse,
    TriageJobRequest,
    TriageJobResponse,
]

for m in models:
    schema = m.model_json_schema()
    path = OUT / f"{m.__name__}.json"
    path.write_text(json.dumps(schema, indent=2))
    print(f"wrote {path.relative_to(OUT.parent.parent.parent)}")
