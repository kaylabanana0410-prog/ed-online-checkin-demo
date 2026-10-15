import logging, tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from .. import config
from ..services.ratelimit import limit
from ..dependencies import get_card_validator, get_ocr_service
from ..services.ocr_service import OCRResult

log = logging.getLogger("documents")  # never log filenames, contents or extracted values
router = APIRouter(prefix="/api/documents", tags=["documents"], dependencies=[Depends(limit("scan"))])
MAGIC = {b"\xff\xd8\xff": "jpg", b"\x89PNG\r\n\x1a\n": "png"}
MESSAGES = {
    "ok": "We read these details from your card. Check each one and fix anything that is wrong. Nothing has been verified.",
    "low_confidence": "The image may be blurry or have glare. Check the details carefully, retake the photo, or enter them manually.",
    "failed": "We could not read the card. Retake the photo in good light without glare, or enter the details manually.",
}

def _label(c: float) -> str:
    return "high" if c >= 0.85 else "medium" if c >= 0.6 else "low"

@router.post("/card-scan")
async def card_scan(response: Response, file: UploadFile = File(...), ocr=Depends(get_ocr_service)):
    response.headers["Cache-Control"] = "no-store"
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(415, "Use a JPEG or PNG image.")
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That file is over 5 MB. Choose a smaller image.")
    if not data:
        raise HTTPException(400, "The file is empty.")
    ext = next((e for m, e in MAGIC.items() if data.startswith(m)), None)
    if not ext:  # content type can be spoofed: check the file's own signature
        raise HTTPException(415, "That file is not a valid JPEG or PNG image.")
    with tempfile.TemporaryDirectory(prefix="cardscan_") as d:  # private dir, removed on exit
        path = Path(d) / f"card.{ext}"  # server-chosen name: the client filename is never used
        path.write_bytes(data)
        try:
            result = await run_in_threadpool(ocr.extract, path)
        except Exception as e:
            log.warning("ocr_failed: %s", type(e).__name__)
            result = OCRResult([], "failed")
    del data
    return {
        "quality": result.quality, "simulated": result.simulated,
        "manual_entry_needed": not result.fields, "message": MESSAGES.get(result.quality, MESSAGES["failed"]),
        "fields": [{"name": f.name, "value": f.value, "confidence": round(f.confidence, 2),
                    "confidence_label": _label(f.confidence), "verified": False, "needs_confirmation": True}
                   for f in result.fields],
    }

class CardIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    health_number: str = Field(max_length=20)  # used in memory only: never stored, logged, or echoed in full
    version_code: str | None = Field(None, max_length=2)

@router.post("/card-validate")
def card_validate(body: CardIn, response: Response, validator=Depends(get_card_validator)):
    response.headers["Cache-Control"] = "no-store"
    digits = "".join(c for c in body.health_number if c.isdigit())
    r = validator.check_format(digits, (body.version_code or "").upper() or None)
    return {"format_valid": r.format_valid, "masked_number": "******" + digits[-4:] if len(digits) >= 4 else "",
            "eligibility": r.eligibility, "simulated": r.simulated,
            "message": "Simulated format check only. Hospital staff confirm eligibility through authorized processes."}
