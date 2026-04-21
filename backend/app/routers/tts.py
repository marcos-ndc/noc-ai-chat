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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"
TTS_VOICE      = os.getenv("TTS_VOICE",  "onyx")
TTS_MODEL      = os.getenv("TTS_MODEL",  "tts-1-hd")
TTS_SPEED      = float(os.getenv("TTS_SPEED", "0.92"))

# ── ElevenLabs TTS ────────────────────────────────────────────────────────────
EL_API_KEY     = os.getenv("ELEVENLABS_API_KEY", "")
EL_MODEL       = os.getenv("ELEVENLABS_MODEL",    "eleven_flash_v2_5")
EL_VOICE_ID    = os.getenv("ELEVENLABS_VOICE_ID", "")
EL_BASE_URL    = "https://api.elevenlabs.io/v1"

SSL_VERIFY = os.getenv("ANTHROPIC_SSL_VERIFY", "true").lower() != "false"

# ── Vozes pt-BR recomendadas (IDs buscados via API na sua conta) ──────────────
# Esses são IDs da Voice Library pública do ElevenLabs para pt-BR
# O endpoint /tts/voices busca os disponíveis na sua conta
ELEVENLABS_PTBR_PRESETS = {
    "Roberta":       {"id": "XB0fDUnXU5powFXDhCwa", "gender": "feminino",  "desc": "Jovem e amigável — ideal para conversação"},
    "Rafael Valente": {"id": "z9fAnlkpzviPz146aGWa", "gender": "masculino", "desc": "Narrador profissional brasileiro — voz cativante"},
    "Borges":        {"id": "pMsXgVXv3BLzUgSXRplE", "gender": "masculino", "desc": "Voz jornalística calma — bom para NOC"},
    "Raquel":        {"id": "ODq5zmih8GrVes37Dizd", "gender": "feminino",  "desc": "Expressiva e jovial — conversacional"},
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
    text = req.text[:4000].strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texto vazio")

    if req.provider == "elevenlabs":
        return await _speak_elevenlabs(text, req.voice, req.model)
    else:
        return await _speak_openai(text, req.voice, req.speed, req.model)


async def _speak_openai(text: str, voice: str, speed: float, model: str) -> Response:
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY não configurada")

    v = voice if voice in OPENAI_VOICES else TTS_VOICE
    m = model if model in ("tts-1", "tts-1-hd") else TTS_MODEL

    async with httpx.AsyncClient(timeout=30.0, verify=SSL_VERIFY) as client:
        resp = await client.post(
            OPENAI_TTS_URL,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={"model": m, "input": text, "voice": v, "speed": speed, "response_format": "mp3"},
        )
        resp.raise_for_status()
        return Response(content=resp.content, media_type="audio/mpeg",
                        headers={"X-TTS-Provider": "openai", "X-TTS-Voice": v})


async def _speak_elevenlabs(text: str, voice_id: str, model: str) -> Response:
    if not EL_API_KEY:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY não configurada")

    vid = voice_id or EL_VOICE_ID or list(ELEVENLABS_PTBR_PRESETS.values())[0]["id"]
    mid = model or EL_MODEL

    url = f"{EL_BASE_URL}/text-to-speech/{vid}"
    async with httpx.AsyncClient(timeout=30.0, verify=SSL_VERIFY) as client:
        resp = await client.post(
            url,
            headers={"xi-api-key": EL_API_KEY, "Content-Type": "application/json"},
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
    result: dict = {
        "openai": {
            "available": bool(OPENAI_API_KEY),
            "default_voice": TTS_VOICE,
            "default_model": TTS_MODEL,
            "voices": OPENAI_VOICES,
            "models": {"tts-1": "Rápido", "tts-1-hd": "Alta qualidade (recomendado)"},
        },
        "elevenlabs": {
            "available": bool(EL_API_KEY),
            "default_voice_id": EL_VOICE_ID,
            "default_model": EL_MODEL,
            "voices": {},
            "models": {
                "eleven_flash_v2_5": "Flash — ultra-baixa latência ~75ms (recomendado para NOC)",
                "eleven_multilingual_v2": "Multilingual v2 — máxima qualidade",
                "eleven_v3": "v3 — mais expressivo",
            },
        },
    }

    # Fetch voices from ElevenLabs API if key is configured
    if EL_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=SSL_VERIFY) as client:
                r = await client.get(
                    f"{EL_BASE_URL}/voices",
                    headers={"xi-api-key": EL_API_KEY},
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
    return {
        "openai":      bool(OPENAI_API_KEY),
        "elevenlabs":  bool(EL_API_KEY),
        "available":   bool(OPENAI_API_KEY or EL_API_KEY),
        "default_provider": "elevenlabs" if EL_API_KEY else ("openai" if OPENAI_API_KEY else "browser"),
    }
