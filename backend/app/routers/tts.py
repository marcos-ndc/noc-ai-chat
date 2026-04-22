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
# Vozes disponíveis na conta — inclui premade + vozes configuradas pelo usuário
ELEVENLABS_PTBR_PRESETS = {
    # Vozes da conta do usuário
    "Voz 1":  {"id": "czvzJwIVS2asEKnthV40", "gender": "?", "desc": "Voz personalizada 1"},
    "Voz 2":  {"id": "jkiD8IhCU1i2V7VvmNwi", "gender": "?", "desc": "Voz personalizada 2"},
    "Voz 3":  {"id": "Qrdut83w0Cr152Yb4Xn3", "gender": "?", "desc": "Voz personalizada 3"},
    "Voz 4":  {"id": "liAlPCvGDJ0qsfPupueo", "gender": "?", "desc": "Voz personalizada 4"},
    "Voz 5":  {"id": "MZxV5lN3cv7hi1376O0m", "gender": "?", "desc": "Voz personalizada 5"},
    "Voz 6":  {"id": "CbNfj17erd366KLOAufd", "gender": "?", "desc": "Voz personalizada 6"},
    # Vozes premade disponíveis em todos os planos
    "Liam":   {"id": "TX3LPaxmHKxFdv7VOQHJ", "gender": "masculino", "desc": "Jovem masculino — direto"},
    "Laura":  {"id": "FGY2WhTYpPnrIDTdsKH5", "gender": "feminino",  "desc": "Jovem feminina — conversacional"},
    "Charlie":{"id": "IKne3meq5aSn9XLyUdCD", "gender": "masculino", "desc": "Masculina natural em pt-BR"},
    "Alice":  {"id": "Xb7hH8MSUJpSbSDYk0k2", "gender": "feminino",  "desc": "Feminina expressiva"},
    "George": {"id": "JBFqnCBsd6RMkjVDRZzb", "gender": "masculino", "desc": "Grave e autoritativa — NOC"},
    "Matilda":{"id": "XrExE9yKIg1WjnnlVkGX", "gender": "feminino",  "desc": "Feminina amigável"},
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
    provider: str   = ""    # "openai" | "elevenlabs" | "" = auto-select
    voice:    str   = ""    # voice name/id
    speed:    float = 0.92  # will be overridden by _cfg() in handler
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
        if resp.status_code != 200:
            detail = resp.text[:300] if resp.text else f"HTTP {resp.status_code}"
            raise HTTPException(status_code=resp.status_code,
                                detail=f"OpenAI TTS error: {detail}")
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
                # language_code omitted — eleven_flash_v2_5 auto-detects pt-BR from text
            },
        )
        if resp.status_code != 200:
            detail = resp.text[:300] if resp.text else f"HTTP {resp.status_code}"
            raise HTTPException(status_code=resp.status_code,
                                detail=f"ElevenLabs error: {detail}")
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
                    # Build a set of all voice IDs from account
                    account_ids = {v["voice_id"] for v in data.get("voices", [])}
                    # Add account voices
                    for v in data.get("voices", []):
                        labels = v.get("labels", {})
                        voices[v["voice_id"]] = {
                            "name":   v["name"],
                            "desc":   v.get("description", labels.get("description", "")),
                            "gender": labels.get("gender", ""),
                            "accent": labels.get("accent", ""),
                        }
                    # Always add ALL presets — if already in account, enrich with real name
                    for preset_name, info in ELEVENLABS_PTBR_PRESETS.items():
                        vid = info["id"]
                        if vid in voices:
                            # Voice is in account — keep real name, add preset label
                            voices[vid]["preset_label"] = preset_name
                        else:
                            # Not in account yet — add as preset
                            voices[vid] = {
                                "name":   preset_name,
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


@router.get("/debug")
async def tts_debug():
    """Debug: mostra quais variáveis de ambiente o backend está lendo."""
    import os
    return {
        "OPENAI_API_KEY":      "✅ configurada" if os.getenv("OPENAI_API_KEY") else "❌ vazia",
        "ELEVENLABS_API_KEY":  "✅ configurada" if os.getenv("ELEVENLABS_API_KEY") else "❌ vazia",
        "ELEVENLABS_MODEL":    os.getenv("ELEVENLABS_MODEL", "não definida"),
        "ELEVENLABS_VOICE_ID": os.getenv("ELEVENLABS_VOICE_ID", "não definida"),
        "TTS_VOICE":           os.getenv("TTS_VOICE", "não definida"),
        "TTS_MODEL":           os.getenv("TTS_MODEL", "não definida"),
        "_cfg()": str(_cfg()),
    }

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
