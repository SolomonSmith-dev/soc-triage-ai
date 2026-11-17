"""Write the ZeroGPU Space's files for one commit of this repo.

    python deploy/hf-space-zerogpu/bundle.py <40-character commit hash> <output directory>

Every file comes from that commit, not the working tree: app.py, README.md, requirements.txt with its three
GitHub archive URLs pinned to the commit, and the harness cassettes and cases that cached mode replays. The
two data directories in the output are replaced, so recordings dropped from the repo leave the Space too.
Push the output directory's contents to the Space repo.
"""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = "deploy/hf-space-zerogpu"
DATA = ("tests/harness/cassettes", "tests/harness/cases")


def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def bundle(sha: str, out: Path) -> dict[str, int]:
    """Returns how many cassettes and cases the Space will serve from."""
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise SystemExit(f"expected a 40-character commit hash, got {sha!r}")
    out.mkdir(parents=True, exist_ok=True)
    for name in ("app.py", "README.md"):
        (out / name).write_bytes(_git("show", f"{sha}:{HERE}/{name}"))
    requirements, n = re.subn(r"/archive/main\.tar\.gz#", f"/archive/{sha}.tar.gz#",
                              _git("show", f"{sha}:{HERE}/requirements.txt").decode())
    if n != 3:
        raise SystemExit(f"expected 3 archive URLs on main in requirements.txt, replaced {n}")
    (out / "requirements.txt").write_text(requirements)
    for d in DATA:
        shutil.rmtree(out / d, ignore_errors=True)
    with tarfile.open(fileobj=io.BytesIO(_git("archive", "--format=tar", sha, *DATA))) as tar:
        # the "data" filter exists from Python 3.12 (and in 3.10/3.11 security releases); the archive is this repo's
        tar.extractall(out, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return {"cassettes": len(list((out / DATA[0]).glob("*.json"))), "cases": len(list((out / DATA[1]).rglob("*.yaml")))}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    counts = bundle(sys.argv[1], Path(sys.argv[2]))
    print(f"wrote app.py, README.md, requirements.txt pinned to {sys.argv[1][:7]}; "
          f"{counts['cassettes']} cassettes, {counts['cases']} cases")
