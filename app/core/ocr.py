# ============================================================
# core/ocr.py
# ------------------------------------------------------------
# OCR abstraction. Extracts insurance fields from a document.
#
# Providers supported:
#   - "none"      : not configured, extraction is disabled
#   - "mindee"    : Mindee API (best for insurance)
#   - "google"    : Google Cloud Vision
#   - "aws"       : AWS Textract
#
# Configuration lives in the platform_settings table.
#
# The caller gets back a dict:
#   {
#     "provider": str, "policy_number": str?, "coverage_amount": str?,
#     "effective_date": str?, "expiration_date": str?, "raw": {...}
#   }
# ============================================================

import json
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.platform_settings import PlatformSetting


# ------------------------------------------------------------
# Load configuration
# ------------------------------------------------------------
def _get_setting(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
    if not row or row.value is None:
        return default
    return row.value


def get_ocr_config(db: Session) -> dict:
    """Return the OCR configuration from platform_settings."""
    return {
        "provider": _get_setting(db, "ocr.provider", "none"),
        "mindee_api_key": _get_setting(db, "ocr.mindee_api_key", ""),
        "google_api_key": _get_setting(db, "ocr.google_api_key", ""),
        "aws_access_key": _get_setting(db, "ocr.aws_access_key", ""),
        "aws_secret_key": _get_setting(db, "ocr.aws_secret_key", ""),
        "aws_region": _get_setting(db, "ocr.aws_region", "us-east-1"),
    }


# ------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------
def extract_insurance_fields(db: Session, file_path: str) -> dict:
    """
    Extract insurance fields from a document.
    Returns a dict with `status` and extracted fields.
    """
    config = get_ocr_config(db)
    provider = (config["provider"] or "none").lower()

    if provider == "none":
        return {
            "status": "not_configured",
            "message": "OCR is not configured. Set it up in Settings → OCR.",
        }

    if not Path(file_path).exists():
        return {"status": "error", "message": "File not found"}

    try:
        if provider == "mindee":
            return _extract_mindee(config, file_path)
        elif provider == "google":
            return _extract_google(config, file_path)
        elif provider == "aws":
            return _extract_aws(config, file_path)
        else:
            return {"status": "error", "message": f"Unknown provider: {provider}"}
    except Exception as e:
        return {"status": "error", "message": f"{type(e).__name__}: {str(e)}"}


# ------------------------------------------------------------
# Mindee
# ------------------------------------------------------------
def _extract_mindee(config: dict, file_path: str) -> dict:
    try:
        import requests
    except ImportError:
        return {"status": "error", "message": "requests library not installed"}

    api_key = config.get("mindee_api_key")
    if not api_key:
        return {"status": "error", "message": "Mindee API key not set"}

    # Mindee's insurance card / document extraction endpoint
    # Using the generic "custom document" endpoint. Replace with a
    # specific model endpoint (e.g. US Health Insurance Card) if you
    # have a Mindee account with a trained model.
    url = "https://api.mindee.net/v1/products/mindee/insurance_card/v1/predict"

    with open(file_path, "rb") as f:
        files = {"document": f}
        headers = {"Authorization": f"Token {api_key}"}
        resp = requests.post(url, files=files, headers=headers, timeout=30)

    if resp.status_code != 200:
        return {
            "status": "error",
            "message": f"Mindee error {resp.status_code}: {resp.text[:200]}",
        }

    data = resp.json()
    predictions = data.get("document", {}).get("inference", {}).get("prediction", {})

    def _val(field_name: str):
        f = predictions.get(field_name)
        if isinstance(f, dict):
            return f.get("value")
        return None

    return {
        "status": "success",
        "provider": "mindee",
        "policy_number": _val("policy_number"),
        "coverage_amount": _val("coverage_amount"),
        "effective_date": _val("effective_date"),
        "expiration_date": _val("expiration_date"),
        "provider_name": _val("provider"),
        "raw": data,
    }


# ------------------------------------------------------------
# Google Cloud Vision
# ------------------------------------------------------------
def _extract_google(config: dict, file_path: str) -> dict:
    try:
        import base64
        import requests
    except ImportError:
        return {"status": "error", "message": "Missing libraries"}

    api_key = config.get("google_api_key")
    if not api_key:
        return {"status": "error", "message": "Google API key not set"}

    with open(file_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
    payload = {
        "requests": [
            {
                "image": {"content": content},
                "features": [{"type": "TEXT_DETECTION"}],
            }
        ]
    }
    resp = requests.post(url, json=payload, timeout=30)

    if resp.status_code != 200:
        return {
            "status": "error",
            "message": f"Google error {resp.status_code}: {resp.text[:200]}",
        }

    data = resp.json()
    full_text = ""
    try:
        full_text = data["responses"][0]["fullTextAnnotation"]["text"]
    except (KeyError, IndexError):
        pass

    # Parse dates + policy numbers out of raw text with light regex
    import re
    policy_match = re.search(r"[A-Z]{2,4}[- ]?\d{6,12}", full_text)
    date_matches = re.findall(r"\d{1,2}/\d{1,2}/\d{2,4}", full_text)

    return {
        "status": "success",
        "provider": "google",
        "policy_number": policy_match.group(0) if policy_match else None,
        "coverage_amount": None,
        "effective_date": date_matches[0] if date_matches else None,
        "expiration_date": date_matches[1] if len(date_matches) > 1 else None,
        "provider_name": None,
        "raw_text": full_text,
        "raw": data,
    }


# ------------------------------------------------------------
# AWS Textract
# ------------------------------------------------------------
def _extract_aws(config: dict, file_path: str) -> dict:
    try:
        import boto3  # noqa: F401
    except ImportError:
        return {
            "status": "error",
            "message": "boto3 not installed. Run: pip install boto3",
        }
    return {
        "status": "not_implemented",
        "message": "AWS Textract integration is planned. Configure Mindee or Google for now.",
    }