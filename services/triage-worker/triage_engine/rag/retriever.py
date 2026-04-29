"""Embedding-based retrieval over threat intelligence corpus.

Uses sentence-transformers all-MiniLM-L6-v2 for embeddings and numpy
cosine similarity for ranking. No vector DB needed at this corpus size.
"""
import logging
from typing import List, Dict, Tuple, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class ThreatIntelRetriever:
    """Cosine-similarity retriever for SOC alert triage.

    Both corpus chunks and query are embedded with L2 normalization, so
    dot product equals cosine similarity. Returns top_k chunks above
    min_score threshold, sorted by similarity descending.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.chunks: List[Dict] = []
        self.embeddings: Optional[np.ndarray] = None

    def index(self, chunks: List[Dict]) -> None:
        """Embed and index corpus chunks."""
        if not chunks:
            raise ValueError("Cannot index empty chunk list")
        self.chunks = chunks
        texts = [c["text"] for c in chunks]
        self.embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        logger.info(f"Indexed {len(chunks)} chunks using {self.model_name}")

    def retrieve(
        self,
        query: str,
        top_k: int = 4,
        min_score: float = 0.20,
    ) -> List[Tuple[Dict, float]]:
        """Return top_k chunks above min_score, sorted by similarity desc."""
        if self.embeddings is None:
            raise RuntimeError("Retriever not indexed. Call .index() first.")
        if not query or not query.strip():
            logger.warning("Empty query passed to retriever")
            return []

        q_emb = self.model.encode(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

        scores = self.embeddings @ q_emb
        top_idx = np.argsort(scores)[::-1][:top_k]
        results = [
            (self.chunks[i], float(scores[i]))
            for i in top_idx
            if scores[i] >= min_score
        ]
        logger.info(
            f"Retrieved {len(results)}/{top_k} chunks for query "
            f"({len(query)} chars), top score: {scores[top_idx[0]]:.3f}"
        )
        return results


if __name__ == "__main__":
    # Smoke test
    from pathlib import Path
    from triage_engine.rag.corpus import load_corpus

    logging.basicConfig(level=logging.INFO)
    retriever = ThreatIntelRetriever()
    corpus_dir = str(Path(__file__).parent.parent / "data" / "threat_intel")
    retriever.index(load_corpus(corpus_dir))

    test_query = "PowerShell encoded command spawned by outlook.exe"
    print(f"\nTest query: {test_query}\n")
    results = retriever.retrieve(test_query, top_k=3)
    for chunk, score in results:
        print(f"[{score:.3f}] {chunk['source']}")
        print(f"  {chunk['text'][:150]}...\n")
