"""SOCTriage accepts an injected client so the harness can wrap the LLM call."""
from triage_engine.triage import SOCTriage


class _FakeBlock:
    def __init__(self, text):
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeMessages:
    def create(self, **kwargs):
        return _FakeResponse(
            '{"severity":"low","confidence":"low","mitre_techniques":[],'
            '"summary":"s","recommended_actions":["a"],"escalate":false,'
            '"reasoning":"r"}'
        )


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


class _FakeRetriever:
    def retrieve(self, query, top_k=4, min_score=0.20):
        return [({"id": "x_0", "source": "x.md", "text": "ctx"}, 0.5)]


def test_injected_client_is_used_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    triage = SOCTriage(client=_FakeClient(), retriever=_FakeRetriever())
    result = triage.triage("PowerShell encoded command from outlook.exe")
    assert result["severity"] == "low"
    assert result["escalate"] is False
