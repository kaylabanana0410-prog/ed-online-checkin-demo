"""Optional OCR. Output is never treated as verified: the patient must confirm or correct every field."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

class OCRError(Exception):
    pass

@dataclass
class OCRField:
    name: str
    value: str
    confidence: float  # 0..1

@dataclass
class OCRResult:
    fields: list = field(default_factory=list)
    quality: str = "ok"  # ok | low_confidence | failed
    simulated: bool = False

class OCRService(Protocol):
    def extract(self, path: Path) -> OCRResult: ...

class MockOCRService:
    """SIMULATED: does not read the image. Returns obviously fake synthetic values."""
    def __init__(self, mode: str = "normal"):
        self.mode = mode
    def extract(self, path: Path) -> OCRResult:
        if self.mode == "failed":
            raise OCRError("simulated failure")
        if self.mode == "blurry":
            return OCRResult([], "low_confidence", True)
        return OCRResult([OCRField("health_number", "1234567890", 0.93), OCRField("version_code", "AB", 0.88),
                          OCRField("expiry_date", "2030-01-31", 0.64)], "ok", True)

_NUM = re.compile(r"\b(\d{4})[ -]?(\d{3})[ -]?(\d{3})\b(?:\s*([A-Z]{2})\b)?")
_DATE = re.compile(r"\b(20\d{2})[/-](\d{2})[/-](\d{2})\b")

def parse_card_text(text: str, avg_confidence: float) -> OCRResult:
    """Best-effort parsing of OCR text. Must be validated against real card layouts before real use."""
    fields = []
    m = _NUM.search(text)
    if m:
        fields.append(OCRField("health_number", "".join(m.group(1, 2, 3)), avg_confidence))
        if m.group(4):
            fields.append(OCRField("version_code", m.group(4), avg_confidence * 0.9))
    d = _DATE.search(text)
    if d:
        fields.append(OCRField("expiry_date", f"{d[1]}-{d[2]}-{d[3]}", avg_confidence * 0.8))
    if not fields:
        return OCRResult([], "failed")
    return OCRResult(fields, "ok" if avg_confidence >= 0.7 else "low_confidence")

class TesseractOCRService:
    """Real local OCR (no data leaves the server). Optional: pip install pytesseract pillow, plus Tesseract."""
    def extract(self, path: Path) -> OCRResult:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as e:
            raise OCRError("tesseract not installed") from e
        Image.MAX_IMAGE_PIXELS = 25_000_000  # reject decompression bombs
        data = pytesseract.image_to_data(Image.open(path), output_type=pytesseract.Output.DICT)
        pairs = [(w, float(c)) for w, c in zip(data["text"], data["conf"]) if w.strip() and float(c) >= 0]
        avg = (sum(c for _, c in pairs) / len(pairs) / 100) if pairs else 0.0
        return parse_card_text(" ".join(w for w, _ in pairs), avg)
