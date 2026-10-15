from functools import lru_cache
from . import config
from .services.ai_assistant import MockAIAssistant
from .services.hospital_integration import MockClinicalWorkflow
from .services.safety_rules import RulesEngine

@lru_cache
def get_rules_engine() -> RulesEngine:
    return RulesEngine.from_file(config.RULES_PATH)

def get_ai_assistant():
    return MockAIAssistant(config.MOCK_AI_MODE)  # swap for an approved provider later

def get_clinical_workflow():
    return MockClinicalWorkflow()

from .services.hospital_integration import MockCardValidation
from .services.ocr_service import MockOCRService, TesseractOCRService

def get_ocr_service():
    return TesseractOCRService() if config.OCR_BACKEND == "tesseract" else MockOCRService(config.MOCK_OCR_MODE)

def get_card_validator():
    return MockCardValidation()
