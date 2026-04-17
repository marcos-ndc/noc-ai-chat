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
SSL_VERIFY      = os.getenv("ANTHROPIC_SSL_VERIFY", "true").lower() != "false"

# Voz padrão: "onyx" — grave, autoritativa, similar ao Jarvis
# Outras opções: alloy, echo, fable, nova, shimmer
TTS_VOICE  = os.getenv("TTS_VOICE", "onyx")
TTS_MODEL  = os.getenv("TTS_MODEL", "tts-1")     # tts-1 (rápido) ou tts-1-hd (qualidade)
TTS_SPEED  = float(os.getenv("TTS_SPEED", "0.95")) # 0.25–4.0, ligeiramente mais lento = mais grave


class TTSRequest(BaseModel):
    text: str
    voice: str = TTS_VOICE
    speed: float = TTS_SPEED


@router.post("/speak", response_class=Response)
async def speak(req: TTSRequest):
    """
    Converte texto em fala via OpenAI TTS.
    Retorna áudio MP3 pronto para reprodução.
    """
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY não configurada. Configure no .env para usar voz premium."
        )

    # Limita tamanho do texto (OpenAI TTS aceita até 4096 chars)
    text = req.text[:4000].strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texto vazio")

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            verify=SSL_VERIFY,
        ) as client:
            resp = await client.post(
                OPENAI_TTS_URL,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": TTS_MODEL,
                    "input": text,
                    "voice": req.voice,
                    "speed": req.speed,
                    "response_format": "mp3",
                },
            )
            resp.raise_for_status()

            return Response(
                content=resp.content,
                media_type="audio/mpeg",
                headers={
                    "Cache-Control": "no-cache",
                    "X-TTS-Voice": req.voice,
                    "X-TTS-Model": TTS_MODEL,
                },
            )

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenAI TTS error: {e.response.text[:200]}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")


@router.get("/status")
async def tts_status():
    """Verifica se TTS premium está disponível."""
    return {
        "available": bool(OPENAI_API_KEY),
        "voice": TTS_VOICE,
        "model": TTS_MODEL,
        "speed": TTS_SPEED,
        "voices": {
            "onyx":    "Grave e autoritativa — recomendada (similar ao Jarvis)",
            "echo":    "Masculina equilibrada",
            "fable":   "Expressiva e suave",
            "alloy":   "Neutra e clara",
            "nova":    "Feminina e amigável",
            "shimmer": "Feminina e suave",
        }
    }
