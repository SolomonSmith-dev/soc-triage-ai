"""Loads threat intel markdown corpus and chunks documents by paragraph."""
import logging
import re
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

TECH_ID = re.compile(r"T\d{4}(?:\.\d{3})?")


def section_technique_ids(chunks: List[Dict]) -> Dict[str, List[str]]:
    """Map chunk id to the technique IDs that apply to the chunk.

    The paragraph that carries the IDs is often not the one retrieved, so two rules attach them:

    1. A chunk starting with "#" opens a section and sets the IDs named in it (for example
       "## T1110 Brute Force"); the chunks after it inherit them until the next header.
    2. A chunk left with no IDs falls back to its document's "## MITRE Mapping" list, if the
       document has one (ransomware, insider threat, phishing, network anomalies, CVE).

    Pure function of the corpus, no model involved.
    """
    mapping: Dict[str, List[str]] = {}
    for c in chunks:
        if c["text"].lstrip().startswith("## MITRE Mapping"):
            mapping[c["source"]] = sorted(set(TECH_ID.findall(c["text"])))

    out: Dict[str, List[str]] = {}
    current: List[str] = []
    source = None
    for c in chunks:
        if c["source"] != source:
            source, current = c["source"], []
        own = sorted(set(TECH_ID.findall(c["text"])))
        if c["text"].lstrip().startswith("#"):
            current = own
        ids = sorted(set(current) | set(own))
        out[c["id"]] = ids if ids else mapping.get(c["source"], [])
    return out


def load_corpus(corpus_dir: str = "data/threat_intel") -> List[Dict]:
    """Load all .md files from corpus_dir. Chunk by paragraph.

    Returns list of dicts with keys: id, source, text.
    Raises FileNotFoundError if corpus directory missing.
    Raises RuntimeError if no usable chunks found.
    """
    corpus_path = Path(corpus_dir)
    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus directory not found: {corpus_dir}")

    chunks: List[Dict] = []
    for path in sorted(corpus_path.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for i, para in enumerate(text.split("\n\n")):
            para = para.strip()
            # Skip empty, too-short, or too-long chunks
            if 80 <= len(para) <= 1500:
                chunks.append({
                    "id": f"{path.stem}_{i}",
                    "source": path.name,
                    "text": para,
                })

    if not chunks:
        raise RuntimeError(f"No usable chunks found in {corpus_dir}")

    logger.info(f"Loaded {len(chunks)} chunks from {corpus_dir}")
    return chunks


if __name__ == "__main__":
    # Smoke test
    logging.basicConfig(level=logging.INFO)
    chunks = load_corpus()
    print(f"\nLoaded {len(chunks)} chunks")
    print(f"First chunk source: {chunks[0]['source']}")
    print(f"First chunk preview: {chunks[0]['text'][:200]}...")
