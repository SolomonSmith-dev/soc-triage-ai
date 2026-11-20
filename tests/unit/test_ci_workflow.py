"""F7: CI must fail closed when retrieval_results.json is missing."""
from pathlib import Path

CI = Path(".github/workflows/ci.yml").read_text()
EVAL_TEST = Path("tests/unit/test_retrieval_eval.py").read_text()


def test_retrieval_check_does_not_pass_when_results_file_missing():
    assert "no committed retrieval_results.json yet" not in CI
    assert "if [ -f tests/harness/retrieval_results.json ]" not in CI
    assert (
        "python -m tests.harness.retrieval_eval --check tests/harness/retrieval_results.json"
        in CI
    )


def test_committed_results_unit_test_does_not_skip_when_missing():
    assert 'pytest.skip("retrieval_results.json not committed yet")' not in EVAL_TEST


def test_ci_gate_needs_every_job_and_fails_closed():
    start = CI.index("  ci-gate:")
    block = CI[start:]
    assert "if: always()" in block
    assert '*" failure "*' in block
    assert '*" cancelled "*' in block
    assert '*" skipped "*' in block
    for job in (
        "unit-tests",
        "api-tests",
        "harness-replay",
        "retrieval-eval",
        "demo-image",
        "space-app",
    ):
        assert job in block
