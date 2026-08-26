from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .nutrition_capture import NutritionExtraction


@dataclass
class CaptureImageResult:
    upload_id: str
    filename: str
    content_type: str
    image_path: Path
    extraction: NutritionExtraction
    confidence: str


@dataclass
class CaptureSessionResult:
    capture_id: str
    images: list[CaptureImageResult] = field(default_factory=list)
    extraction: dict[str, float | str | None] = field(default_factory=dict)
    field_confidence: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    source_upload_ids: dict[str, str] = field(default_factory=dict)


_CONFIDENCE_RANK = {"unknown": 0, "needs_review": 1, "high": 2, "user_verified": 3}


def merge_extractions(capture_id: str, images: list[CaptureImageResult]) -> CaptureSessionResult:
    merged = CaptureSessionResult(capture_id=capture_id, images=images)
    for image in images:
        for warning in image.extraction.warnings:
            if warning not in merged.warnings:
                merged.warnings.append(warning)
        for field_name, value in image.extraction.values.items():
            if value is None or value == "":
                continue
            incoming_confidence = image.extraction.confidence.get(field_name, image.confidence)
            current_confidence = merged.field_confidence.get(field_name, "unknown")
            if field_name not in merged.extraction or _CONFIDENCE_RANK.get(incoming_confidence, 0) > _CONFIDENCE_RANK.get(current_confidence, 0):
                merged.extraction[field_name] = value
                merged.field_confidence[field_name] = incoming_confidence
                merged.source_upload_ids[field_name] = image.upload_id
            elif merged.extraction.get(field_name) != value and _CONFIDENCE_RANK.get(incoming_confidence, 0) == _CONFIDENCE_RANK.get(current_confidence, 0):
                warning = f"Conflicting {field_name.replace('_', ' ')} values were detected across uploaded images"
                if warning not in merged.warnings:
                    merged.warnings.append(warning)
    return merged


def capture_response(result: CaptureSessionResult) -> dict[str, Any]:
    return {
        "capture_id": result.capture_id,
        "status": "awaiting_review",
        "review_required": True,
        "images": [
            {
                "upload_id": item.upload_id,
                "filename": item.filename,
                "content_type": item.content_type,
                "confidence": item.confidence,
            }
            for item in result.images
        ],
        "extraction": result.extraction,
        "field_confidence": result.field_confidence,
        "source_upload_ids": result.source_upload_ids,
        "warnings": result.warnings,
        "message": "Local OCR completed for all images. Review every extracted value before saving.",
    }
