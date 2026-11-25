"""Decode a short in-memory recording and transcribe with local SenseVoice."""

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from threading import BoundedSemaphore

import numpy as np

MAX_AUDIO_BYTES = 2 * 1024 * 1024
SAMPLE_RATE = 16000
MAX_AUDIO_SECONDS = 16
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "speech" / "sensevoice"
FORMATS = {
    "audio/webm": "matroska",
    "audio/ogg": "ogg",
    "audio/mp4": "mov",
    "audio/3gpp": "mov",
    "audio/amr": "amr",
    "audio/aac": "aac",
    "audio/wav": "wav",
}
_worker = BoundedSemaphore(1)


class SpeechUnavailable(RuntimeError):
    pass


class SpeechBusy(RuntimeError):
    pass


class InvalidAudio(ValueError):
    pass


@lru_cache(maxsize=1)
def _recognizer():
    model_dir = Path(os.environ.get("SHIYANG_SPEECH_MODEL_DIR") or DEFAULT_MODEL_DIR)
    model = model_dir / "model.int8.onnx"
    tokens = model_dir / "tokens.txt"
    if not (model.is_file() and tokens.is_file()):
        raise SpeechUnavailable()
    try:
        from sherpa_onnx import OfflineRecognizer

        return OfflineRecognizer.from_sense_voice(
            model=str(model), tokens=str(tokens), language="auto", use_itn=True,
            num_threads=2, sample_rate=SAMPLE_RATE, debug=False,
        )
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise SpeechUnavailable() from exc


def _decode(audio: bytes, content_type: str) -> np.ndarray:
    ffmpeg = shutil.which(os.environ.get("SHIYANG_FFMPEG") or "ffmpeg")
    if not ffmpeg:
        raise SpeechUnavailable()
    try:
        decoded = subprocess.run(
            [
                ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                "-protocol_whitelist", "pipe", "-threads", "1", "-f", FORMATS[content_type],
                "-i", "pipe:0", "-map", "0:a:0", "-vn", "-sn", "-dn",
                "-t", str(MAX_AUDIO_SECONDS + 1), "-ac", "1", "-ar", str(SAMPLE_RATE),
                "-f", "s16le", "pipe:1",
            ],
            input=audio, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except OSError as exc:
        raise SpeechUnavailable() from exc
    except subprocess.TimeoutExpired as exc:
        raise InvalidAudio("音频无法读取，请重新录制。") from exc
    if decoded.returncode or not decoded.stdout:
        raise InvalidAudio("音频无法读取，请重新录制。")
    samples = np.frombuffer(decoded.stdout, dtype="<i2")
    if len(samples) > SAMPLE_RATE * MAX_AUDIO_SECONDS:
        raise InvalidAudio("录音过长，请分段输入。")
    return samples.astype(np.float32) / 32768


def transcribe(audio: bytes, content_type: str) -> str:
    if not _worker.acquire(blocking=False):
        raise SpeechBusy()
    try:
        samples = _decode(audio, content_type)
        if len(samples) < SAMPLE_RATE // 4 or np.max(np.abs(samples)) < 0.003:
            return ""
        recognizer = _recognizer()
        stream = recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples)
        recognizer.decode_stream(stream)
        return stream.result.text.strip()
    finally:
        _worker.release()
