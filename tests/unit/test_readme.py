"""README numbers come from the committed JSON, and the generated blocks are current."""
import json
import re
import subprocess
import sys
from pathlib import Path

README = Path("README.md").read_text()
R = json.loads(Path("tests/harness/retrieval_results.json").read_text())["metrics"]


def test_generated_blocks_are_current():
    assert subprocess.run([sys.executable, "-m", "tests.harness.readme_results", "--check"]).returncode == 0


def test_prose_numbers_match_retrieval_json():
    assert f"none of the {R['answerable_queries']} real alerts" in README
    assert f"{R['refusal_tp']} of {R['refusal_tp'] + R['refusal_fn']} out-of-corpus inputs are refused" in README
    assert f"precision {R['refusal_precision']}" in README and f"recall {R['refusal_recall']:.2f}" in README


def test_no_stale_seven_of_seven_badge():
    badges = README.split("<!-- BADGES:END -->")[0]
    assert "7%2F7" not in badges and "7/7" not in badges


def test_placeholders_are_only_the_demo_link():
    assert re.findall(r"[A-Z_]+_PLACEHOLDER", README) == ["DEMO_URL_PLACEHOLDER"]


def test_no_em_dashes_in_prose():
    for p in ("README.md", "model_card.md", "docs/deploy-hf.md", "docs/triage-2026-10.md", "docs/ROADMAP.md",
              "docs/decisions/0001-ship-v2-core.md", "tests/harness/README.md", "tests/harness/RESULTS.md"):
        assert "\u2014" not in Path(p).read_text(), p
