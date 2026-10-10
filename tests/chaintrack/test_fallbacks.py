"""Deployment fallbacks: model outage and no Transcribe must not block a handover."""
import os

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")

from capture.handlers import wiring  # noqa: E402


def test_bedrock_failure_falls_back_to_deterministic_reader(monkeypatch):
    from extract import bedrock_extract as bx

    monkeypatch.delenv("EXTRACT_MODE", raising=False)
    monkeypatch.setattr(wiring, "_model_id", lambda: "amazon.nova-lite-v1:0")

    def boom(*_a, **_k):
        raise RuntimeError("AccessDeniedException: account is being verified")

    monkeypatch.setattr(bx, "extract", boom)
    out = wiring.extractor()("4 e-rickshaw batteries from a driver, about 120 kg")
    assert out == bx.extract_offline("4 e-rickshaw batteries from a driver, about 120 kg")
    assert out["uncertain_fields"]


def test_voice_off_returns_no_transcriber(monkeypatch):
    monkeypatch.setenv("VOICE_MODE", "off")
    assert wiring.transcriber() is None
