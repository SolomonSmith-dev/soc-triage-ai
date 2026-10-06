"""RAG components for SOC Triage AI."""
from triage_engine.rag.corpus import load_corpus
from triage_engine.rag.retriever import ThreatIntelRetriever

__all__ = ["load_corpus", "ThreatIntelRetriever"]
