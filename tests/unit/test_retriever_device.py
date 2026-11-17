"""SOC_EMBED_DEVICE pins the embedding device; unset or empty, sentence-transformers chooses. No model weights."""
import triage_engine.rag.retriever as retriever_mod


class FakeModel:
    def __init__(self, name, device=None):
        self.name, self.device = name, device


def test_embedding_device_pin(monkeypatch):
    monkeypatch.setattr(retriever_mod, "SentenceTransformer", FakeModel)
    monkeypatch.delenv("SOC_EMBED_DEVICE", raising=False)
    assert retriever_mod.ThreatIntelRetriever().model.device is None
    monkeypatch.setenv("SOC_EMBED_DEVICE", "")
    assert retriever_mod.ThreatIntelRetriever().model.device is None
    monkeypatch.setenv("SOC_EMBED_DEVICE", "cpu")
    assert retriever_mod.ThreatIntelRetriever().model.device == "cpu"
    assert retriever_mod.ThreatIntelRetriever(device="cuda:1").model.device == "cuda:1"
