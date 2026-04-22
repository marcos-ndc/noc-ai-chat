"""
Router: TTS (Text-to-Speech)
Suporta dois provedores:
  - OpenAI TTS  (onyx, nova, echo, fable, alloy, shimmer)
  - ElevenLabs  (vozes nativas pt-BR: Roberta, Rafael, Borges, Raquel, + outras)

O frontend escolhe o provedor via parâmetro.
API keys ficam no servidor — nunca expostas ao frontend.
"""
import os
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(prefix="/tts", tags=["tts"])

# ── OpenAI TTS ────────────────────────────────────────────────────────────────
OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"
EL_BASE_URL    = "https://api.elevenlabs.io/v1"

# Read at request time so hot-reload picks up new env vars
def _cfg():
    return {
        "openai_key":  os.getenv("OPENAI_API_KEY", ""),
        "tts_voice":   os.getenv("TTS_VOICE",  "onyx"),
        "tts_model":   os.getenv("TTS_MODEL",  "tts-1-hd"),
        "tts_speed":   float(os.getenv("TTS_SPEED", "0.92")),
        "el_key":      os.getenv("ELEVENLABS_API_KEY", ""),
        "el_model":    os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5"),
        "el_voice_id": os.getenv("ELEVENLABS_VOICE_ID", ""),
        "ssl_verify":  os.getenv("ANTHROPIC_SSL_VERIFY", "true").lower() != "false",
    }

# Module-level aliases for backward compat (refreshed per-request via _cfg())
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TTS_VOICE      = os.getenv("TTS_VOICE",  "onyx")
TTS_MODEL      = os.getenv("TTS_MODEL",  "tts-1-hd")
TTS_SPEED      = float(os.getenv("TTS_SPEED", "0.92"))
EL_API_KEY     = os.getenv("ELEVENLABS_API_KEY", "")
EL_MODEL       = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")
EL_VOICE_ID    = os.getenv("ELEVENLABS_VOICE_ID", "")
SSL_VERIFY     = os.getenv("ANTHROPIC_SSL_VERIFY", "true").lower() != "false"

# ── Vozes pt-BR recomendadas (IDs buscados via API na sua conta) ──────────────
# Esses são IDs da Voice Library pública do ElevenLabs para pt-BR
# O endpoint /tts/voices busca os disponíveis na sua conta
# Vozes built-in do ElevenLabs disponíveis em TODOS os planos (premade voices)
# Funcionam bem com pt-BR usando eleven_multilingual_v2 ou eleven_flash_v2_5
ELEVENLABS_PTBR_PRESETS = {
    "Liam":   {"id": "TX3LPaxmHKxFdv7VOQHJ", "gender": "masculino", "desc": "Jovem masculino — direto e natural"},
    "Laura":  {"id": "FGY2WhTYpPnrIDTdsKH5", "gender": "feminino",  "desc": "Jovem feminina — conversacional e clara"},
    "Charlie":{"id": "IKne3meq5aSn9XLyUdCD", "gender": "masculino", "desc": "Masculina casual — natural em pt-BR"},
    "Alice":  {"id": "Xb7hH8MSUJpSbSDYk0k2", "gender": "feminino",  "desc": "Feminina expressiva — boa pronúncia"},
    "George": {"id": "JBFqnCBsd6RMkjVDRZzb", "gender": "masculino", "desc": "Voz grave e autoritativa — estilo NOC"},
    "Matilda":{"id": "XrExE9yKIg1WjnnlVkGX", "gender": "feminino",  "desc": "Feminina amigável e fluente"},
}

OPENAI_VOICES = {
    "onyx":    {"label": "Onyx",    "desc": "Grave e autoritativa — estilo Jarvis", "gender": "masculino"},
    "echo":    {"label": "Echo",    "desc": "Masculina equilibrada — boa dicção",   "gender": "masculino"},
    "fable":   {"label": "Fable",   "desc": "Expressiva — boa para narrativas",     "gender": "masculino"},
    "alloy":   {"label": "Alloy",   "desc": "Neutra e clara",                       "gender": "neutro"},
    "nova":    {"label": "Nova",    "desc": "Feminina natural — pt-BR melhor",      "gender": "feminino"},
    "shimmer": {"label": "Shimmer", "desc": "Feminina suave e acolhedora",          "gender": "feminino"},
}


class TTSRequest(BaseModel):
    text:     str
    provider: str   = "openai"   # "openai" | "elevenlabs"
    voice:    str   = ""         # voice name/id
    speed:    float = TTS_SPEED
    model:    str   = ""


@router.post("/speak", response_class=Response)
async def speak(req: TTSRequest):
    """Converte texto em fala. Suporta OpenAI TTS e ElevenLabs."""
    c    = _cfg()
    text = req.text[:4000].strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texto vazio")

    # Auto-select provider: ElevenLabs if key available and not forced to openai
    provider = req.provider
    if not provider or provider == "auto":
        provider = "elevenlabs" if c["el_key"] else "openai"

    if provider == "elevenlabs":
        return await _speak_elevenlabs(text, req.voice, req.model, c)
    else:
        return await _speak_openai(text, req.voice, req.speed, req.model, c)


async def _speak_openai(text: str, voice: str, speed: float, model: str, c: dict | None = None) -> Response:
    c = c or _cfg()
    if not c["openai_key"]:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY não configurada")

    v = voice if voice in OPENAI_VOICES else c["tts_voice"]
    m = model if model in ("tts-1", "tts-1-hd") else c["tts_model"]

    async with httpx.AsyncClient(timeout=30.0, verify=c["ssl_verify"]) as client:
        resp = await client.post(
            OPENAI_TTS_URL,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={"model": m, "input": text, "voice": v, "speed": speed or c["tts_speed"], "response_format": "mp3"},
        )
        resp.raise_for_status()
        return Response(content=resp.content, media_type="audio/mpeg",
                        headers={"X-TTS-Provider": "openai", "X-TTS-Voice": v})


async def _speak_elevenlabs(text: str, voice_id: str, model: str, c: dict | None = None) -> Response:
    c = c or _cfg()
    if not c["el_key"]:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY não configurada")

    vid = voice_id or c["el_voice_id"] or list(ELEVENLABS_PTBR_PRESETS.values())[0]["id"]
    mid = model or c["el_model"]

    url = f"{EL_BASE_URL}/text-to-speech/{vid}"
    async with httpx.AsyncClient(timeout=30.0, verify=c["ssl_verify"]) as client:
        resp = await client.post(
            url,
            headers={"xi-api-key": c["el_key"], "Content-Type": "application/json"},
            json={
                "text":     text,
                "model_id": mid,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0},
                "language_code": "pt",
            },
        )
        resp.raise_for_status()
        return Response(content=resp.content, media_type="audio/mpeg",
                        headers={"X-TTS-Provider": "elevenlabs", "X-TTS-Voice": vid})


@router.get("/voices")
async def list_voices():
    """Lista todas as vozes disponíveis (OpenAI + ElevenLabs pt-BR)."""
    c = _cfg()
    result: dict = {
        "openai": {
            "available": bool(c["openai_key"]),
            "default_voice": TTS_VOICE,
            "default_model": TTS_MODEL,
            "voices": OPENAI_VOICES,
            "models": {"tts-1": "Rápido", "tts-1-hd": "Alta qualidade (recomendado)"},
        },
        "elevenlabs": {
            "available": bool(c["el_key"]),
            "default_voice_id": c["el_voice_id"],
            "default_model": c["el_model"],
            "voices": {},
            "models": {
                "eleven_flash_v2_5": "Flash — ultra-baixa latência ~75ms (recomendado para NOC)",
                "eleven_multilingual_v2": "Multilingual v2 — máxima qualidade",
                "eleven_v3": "v3 — mais expressivo",
            },
        },
    }

    # Fetch voices from ElevenLabs API if key is configured
    if c["el_key"]:
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=SSL_VERIFY) as client:
                r = await client.get(
                    f"{EL_BASE_URL}/voices",
                    headers={"xi-api-key": c["el_key"]},
                )
                if r.status_code == 200:
                    data = r.json()
                    voices = {}
                    for v in data.get("voices", []):
                        labels = v.get("labels", {})
                        lang   = labels.get("language", "").lower()
                        # Include pt-BR voices + presets
                        if "portuguese" in lang or "brazilian" in lang or "pt" in lang \
                           or v["name"] in ELEVENLABS_PTBR_PRESETS:
                            voices[v["voice_id"]] = {
                                "name":   v["name"],
                                "desc":   v.get("description", labels.get("description", "")),
                                "gender": labels.get("gender", ""),
                                "accent": labels.get("accent", ""),
                            }
                    # Always include presets even if not in account
                    for name, info in ELEVENLABS_PTBR_PRESETS.items():
                        if info["id"] not in voices:
                            voices[info["id"]] = {
                                "name":   name,
                                "desc":   info["desc"],
                                "gender": info["gender"],
                                "accent": "Brasileiro",
                                "preset": True,
                            }
                    result["elevenlabs"]["voices"] = voices
        except Exception as e:
            result["elevenlabs"]["voices"] = {
                v["id"]: {"name": name, "desc": v["desc"], "gender": v["gender"], "accent": "Brasileiro"}
                for name, v in ELEVENLABS_PTBR_PRESETS.items()
            }
            result["elevenlabs"]["error"] = str(e)

    return result


@router.get("/status")
async def tts_status():
    c        = _cfg()
    provider = "elevenlabs" if c["el_key"] else ("openai" if c["openai_key"] else "browser")
    voice    = c["el_voice_id"] or list(ELEVENLABS_PTBR_PRESETS.values())[0]["id"] if c["el_key"] else c["tts_voice"]
    model    = c["el_model"] if c["el_key"] else c["tts_model"]
    return {
        "openai":          bool(c["openai_key"]),
        "elevenlabs":      bool(c["el_key"]),
        "available":       bool(c["openai_key"] or c["el_key"]),
        "default_provider": provider,
        "voice":           voice,
        "model":           model,
        "speed":           TTS_SPEED,
    }
