"""
Router: TTS (Text-to-Speech)
Proxy para OpenAI TTS API — mantém a API key no servidor.
Retorna áudio MP3 para o frontend reproduzir.
Fallback: status 503 quando OPENAI_API_KEY não configurado.
"""
import os
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(prefix="/tts", tags=["tts"])

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"
SSL_VERIFY     = os.getenv("ANTHROPIC_SSL_VERIFY", "true").lower() != "false"

TTS_VOICE = os.getenv("TTS_VOICE", "onyx")
TTS_MODEL = os.getenv("TTS_MODEL", "tts-1-hd")   # tts-1-hd = mais natural e humanizado
TTS_SPEED = float(os.getenv("TTS_SPEED", "0.92")) # ligeiramente mais lento = mais natural

VOICES = {
    "alloy":   {"label": "Alloy",   "desc": "Neutra e clara — boa para leituras técnicas",        "gender": "neutro"},
    "echo":    {"label": "Echo",    "desc": "Masculina equilibrada — boa dicção",                  "gender": "masculino"},
    "fable":   {"label": "Fable",   "desc": "Expressiva e envolvente — ótima para narrativas",     "gender": "masculino"},
    "onyx":    {"label": "Onyx",    "desc": "Grave e autoritativa — estilo Jarvis (recomendada)",  "gender": "masculino"},
    "nova":    {"label": "Nova",    "desc": "Feminina natural e amigável — tom conversacional",    "gender": "feminino"},
    "shimmer": {"label": "Shimmer", "desc": "Feminina suave e acolhedora",                         "gender": "feminino"},
}


class TTSRequest(BaseModel):
    text:  str
    voice: str = TTS_VOICE
    speed: float = TTS_SPEED
    model: str = TTS_MODEL


@router.post("/speak", response_class=Response)
async def speak(req: TTSRequest):
    """Converte texto em fala via OpenAI TTS. Retorna MP3."""
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY não configurada. Adicione ao .env para ativar voz premium."
        )

    text = req.text[:4000].strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texto vazio")

    voice = req.voice if req.voice in VOICES else TTS_VOICE
    model = req.model if req.model in ("tts-1", "tts-1-hd") else TTS_MODEL

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=SSL_VERIFY) as client:
            resp = await client.post(
                OPENAI_TTS_URL,
                headers={
                    "Authorization":  f"Bearer {OPENAI_API_KEY}",
                    "Content-Type":   "application/json",
                },
                json={
                    "model":           model,
                    "input":           text,
                    "voice":           voice,
                    "speed":           req.speed,
                    "response_format": "mp3",
                },
            )
            resp.raise_for_status()
            return Response(
                content=resp.content,
                media_type="audio/mpeg",
                headers={"Cache-Control": "no-cache", "X-TTS-Voice": voice, "X-TTS-Model": model},
            )

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code,
                            detail=f"OpenAI TTS error: {e.response.text[:200]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")


@router.get("/status")
async def tts_status():
    """Verifica disponibilidade e retorna lista de vozes."""
    return {
        "available": bool(OPENAI_API_KEY),
        "voice":     TTS_VOICE,
        "model":     TTS_MODEL,
        "speed":     TTS_SPEED,
        "voices":    VOICES,
        "models": {
            "tts-1":    "Rápido — menor latência, qualidade boa",
            "tts-1-hd": "Alta qualidade — mais natural e humanizado (recomendado)",
        },
    }
