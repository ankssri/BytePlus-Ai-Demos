"""Voiceover for VO mode B (exact script + lip-sync via reference audio).

Two sources (per design decision #3 "both"):
  1. BytePlus TTS endpoint — configurable. The exact request shape depends on the
     TTS product; until the TTS API doc is provided, this makes a best-effort call
     and returns a clear error if TTS_* env is unset. Set TTS_BASE_URL / TTS_MODEL_ID
     (+ any TTS_* extras) in .env.
  2. User-uploaded VO file — handled in app.py: the file is registered as an
     `Audio` asset and passed to Seedance as reference audio. This path needs no TTS.
"""

import requests

from . import config as C


def synthesize(text, voice=None, language="hi", extra=None):
    """
    Best-effort BytePlus TTS call. Returns (result, status); on success result has
    'audio_url' or 'audio_base64'. Shape is intentionally generic — adjust once the
    TTS API doc is provided.
    """
    if not (C.TTS_BASE_URL and C.tts_model()):
        return {"error": "TTS not configured. Set TTS_BASE_URL and TTS_MODEL_ID in .env, "
                         "or use the upload-VO path instead."}, 501
    payload = {"model": C.tts_model(), "input": text, "language": language}
    if voice:
        payload["voice"] = voice
    if extra:
        payload.update(extra)
    try:
        resp = requests.post(C.TTS_BASE_URL, headers=C.bearer_headers(),
                             json=payload, timeout=120)
        data = C.safe_json(resp)
        if resp.status_code not in (200, 201):
            return {"error": data, "http_status": resp.status_code}, resp.status_code
        # Try common response shapes.
        url = (data.get("audio_url") or data.get("url")
               or ((data.get("data") or [{}])[0] or {}).get("url"))
        b64 = data.get("audio") or data.get("audio_base64")
        if url:
            return {"audio_url": url, "raw": data}, 200
        if b64:
            return {"audio_base64": b64, "raw": data}, 200
        return {"error": "No audio in TTS response", "raw": data}, 502
    except Exception as e:
        return {"error": str(e)}, 500
