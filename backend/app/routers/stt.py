"""
Router: STT (Speech-to-Text)
Proxy para OpenAI Whisper API — transcrição de áudio muito mais precisa
que a Web Speech API do Chrome. Resistente a ruído, suporte nativo pt-BR.
"""
import os
import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/stt", tags=["stt"])

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
OPENAI_STT_URL  = "https://api.openai.com/v1/audio/transcriptions"
SSL_VERIFY      = os.getenv("ANTHROPIC_SSL_VERIFY", "true").lower() != "false"
WHISPER_MODEL   = os.getenv("WHISPER_MODEL", "whisper-1")
WHISPER_LANG    = os.getenv("WHISPER_LANG", "pt")   # força pt-BR, evita confusão com outros idiomas


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    prompt: str = Form(default="NOC, Zabbix, Datadog, ThousandEyes, Grafana, alerta, incidente, latência, disponibilidade"),
):
    """
    Transcreve áudio via OpenAI Whisper.
    O parâmetro 'prompt' ajuda o Whisper a reconhecer termos técnicos NOC.
    Retorna: { text: str, language: str, duration: float }
    """
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY não configurada. Configure no .env para usar transcrição premium."
        )

    audio_bytes = await audio.read()
    if len(audio_bytes) < 1000:
        # Áudio muito curto — provavelmente silêncio
        return JSONResponse({"text": "", "language": "pt", "duration": 0})

    filename = audio.filename or "audio.webm"

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=SSL_VERIFY) as client:
            resp = await client.post(
                OPENAI_STT_URL,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": (filename, audio_bytes, audio.content_type or "audio/webm")},
                data={
                    "model":           WHISPER_MODEL,
                    "language":        WHISPER_LANG,
                    "prompt":          prompt,
                    "response_format": "verbose_json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return JSONResponse({
                "text":     data.get("text", "").strip(),
                "language": data.get("language", "pt"),
                "duration": data.get("duration", 0),
            })

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code,
                            detail=f"Whisper error: {e.response.text[:200]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT error: {str(e)}")


@router.get("/status")
async def stt_status():
    """Verifica disponibilidade do STT premium."""
    return {
        "available": bool(OPENAI_API_KEY),
        "model":     WHISPER_MODEL,
        "language":  WHISPER_LANG,
        "provider":  "OpenAI Whisper",
    }
