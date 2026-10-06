import textwrap

import pytest

from tests.harness.loader import CaseLoadError, load_cases, mark_reviewed

GOOD = """
id: X-001
category: phishing
alert: |
  something
expect:
  severity_in: [high]
provenance:
  drafted_by: claude
  reviewed_by: null
"""


def _w(d, name, body):
    (d / f"{name}.yaml").write_text(textwrap.dedent(body))


def test_shipped_suite_is_valid_and_meets_floor():
    cases = load_cases()
    assert len(cases) >= 100
    assert sum(1 for c in cases if c.group == "adversarial:injection") >= 10
    assert sum(1 for c in cases if not c.relevant_chunks) >= 15
    techs = {t.split(".")[0] for c in cases for t in c.expect.techniques_any}
    assert len(techs) >= 15
    sev = {s for c in cases for s in c.expect.severity_in}
    assert sev == {"critical", "high", "medium", "low", "informational"}
    assert all(c.expect.forbid_in_output for c in cases if c.group == "adversarial:injection")


def test_all_errors_collected(tmp_path):
    _w(tmp_path, "X-001", GOOD)
    _w(tmp_path, "X-002", GOOD.replace("X-001", "X-002").replace("[high]", "[urgent]"))
    _w(tmp_path, "X-003", GOOD.replace("X-001", "X-003").replace("alert: |", "bogus: |\nalert: |"))
    with pytest.raises(CaseLoadError) as e:
        load_cases(tmp_path)
    assert len(e.value.errors) == 2


def test_duplicate_id_and_filename_mismatch(tmp_path):
    _w(tmp_path, "X-001", GOOD)
    _w(tmp_path, "X-009", GOOD)
    with pytest.raises(CaseLoadError) as e:
        load_cases(tmp_path)
    assert any("duplicate" in m for m in e.value.errors)


def test_review_status_and_stamping(tmp_path):
    _w(tmp_path, "X-001", GOOD)
    assert not load_cases(tmp_path)[0].human_reviewed
    assert mark_reviewed("someone", tmp_path) == 1
    assert load_cases(tmp_path)[0].human_reviewed
