"""Loads threat intel markdown corpus and chunks documents by paragraph."""
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


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
