"""Discover and validate YAML cases. Collects every error before failing."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from tests.harness.case_schema import Case

CASES_DIR = Path(__file__).parent / "cases"


class CaseLoadError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def load_cases(cases_dir: Path = CASES_DIR) -> list[Case]:
    errors: list[str] = []
    cases: list[Case] = []
    seen: dict[str, Path] = {}
    for path in sorted(Path(cases_dir).rglob("*.yaml")):
        try:
            cases.append(Case.model_validate(yaml.safe_load(path.read_text(encoding="utf-8"))))
        except (ValidationError, yaml.YAMLError, TypeError) as e:
            errors.append(f"{path}: {e}")
            continue
        c = cases[-1]
        if c.id in seen:
            errors.append(f"{path}: duplicate id {c.id} (also {seen[c.id]})")
        seen[c.id] = path
        if path.stem != c.id:
            errors.append(f"{path}: file name must match id {c.id}")
    if errors:
        raise CaseLoadError(errors)
    return cases


def mark_reviewed(reviewer: str, cases_dir: Path = CASES_DIR, only_unreviewed: bool = True) -> int:
    """Stamp provenance.reviewed_by on cases that have none. Returns count changed."""
    changed = 0
    for path in sorted(Path(cases_dir).rglob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        new = re.sub(r"(?m)^  reviewed_by: null$", f"  reviewed_by: {reviewer}", text)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1
    return changed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate harness cases")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--mark-reviewed", metavar="NAME", help="stamp reviewed_by on every unreviewed case")
    args = ap.parse_args(argv)
    if args.mark_reviewed:
        print(f"stamped {mark_reviewed(args.mark_reviewed)} case files")
    try:
        cases = load_cases()
    except CaseLoadError as e:
        print("\n".join(e.errors))
        return 1
    reviewed = sum(c.human_reviewed for c in cases)
    print(f"{len(cases)} cases valid, {reviewed} human-reviewed, {len(cases) - reviewed} pending review")
    return 0


if __name__ == "__main__":
    sys.exit(main())
