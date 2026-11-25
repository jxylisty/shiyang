"""语音转写接口，运行 python -X utf8 -m pytest tests/test_speech.py -q。"""

import io
import wave

from fastapi.testclient import TestClient

from main import app, speech

client = TestClient(app)
ROUTE = "/api/v1/speech/transcribe"


def wav_sample():
    data = io.BytesIO()
    with wave.open(data, "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\x00\x10" * 8000)
    return data.getvalue()


def test_transcription_returns_text_without_caching(monkeypatch):
    def fake_recognize(audio, content_type):
        assert audio.startswith(b"RIFF") and content_type == "audio/wav"
        return "我家有莲子和百合"

    monkeypatch.setattr(speech, "transcribe", fake_recognize)
    result = client.post(ROUTE, content=wav_sample(), headers={"Content-Type": "audio/wav"})
    assert result.status_code == 200
    assert result.json()["data"] == {"text": "我家有莲子和百合"}
    assert result.headers["cache-control"] == "no-store"


def test_transcription_accepts_browser_codec_parameters(monkeypatch):
    monkeypatch.setattr(speech, "transcribe", lambda audio, mime: mime)
    result = client.post(ROUTE, content=b"test", headers={"Content-Type": "audio/webm;codecs=opus"})
    assert result.json()["data"] == {"text": "audio/webm"}


def test_transcription_rejects_wrong_type_empty_and_oversized(monkeypatch):
    monkeypatch.setattr(speech, "MAX_AUDIO_BYTES", 20)
    assert client.post(ROUTE, content=b"x", headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.post(ROUTE, content=b"", headers={"Content-Type": "audio/amr"}).status_code == 400
    audio = (b"x" * 15 for _ in range(2))
    assert client.post(ROUTE, content=audio, headers={"Content-Type": "audio/amr"}).status_code == 413


def test_transcription_reports_missing_model_and_unrecognizable_audio(monkeypatch):
    def fail(*args):
        raise speech.SpeechUnavailable()

    monkeypatch.setattr(speech, "transcribe", fail)
    assert client.post(ROUTE, content=b"x", headers={"Content-Type": "audio/amr"}).status_code == 503

    def no_words(*args):
        return ""

    monkeypatch.setattr(speech, "transcribe", no_words)
    assert client.post(ROUTE, content=b"x", headers={"Content-Type": "audio/amr"}).status_code == 422
