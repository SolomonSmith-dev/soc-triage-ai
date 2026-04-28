"""RAG components for SOC Triage AI."""
from rag.corpus import load_corpus
from rag.retriever import ThreatIntelRetriever

__all__ = ["load_corpus", "ThreatIntelRetriever"]
