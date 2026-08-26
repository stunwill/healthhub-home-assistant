from __future__ import annotations

import io
import logging
from datetime import date, datetime, time, timezone
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytesseract  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .capture_sessions import CaptureImageResult, capture_response, merge_extractions
from .database import get_db
from .main import (
    ALLOWED_CAPTURE_TYPES,
    CAPTURE_DIR,
    MAX_CAPTURE_BYTES,
    create_diary_entry,
    get_profile_or_404,
    local_barcode_food,
    save_reviewed_nutrition_label,
)
from .models import Food
from .nutrition_capture import parse_nutrition_text
from .planning import create_planned_entry
from .planning_schemas import PlannedEntryCreate, PlannedEntryOutput
from .schemas import DiaryEntryCreate, DiaryEntryOutput, FoodOutput, NutritionLabelReviewCreate

router = APIRouter(prefix="/api/v1", tags=["capture"])
DbSession = Annotated[Session, Depends(get_db)]
logger = logging.getLogger("healthhub.performance")
MAX_CAPTURE_IMAGES = 8


def _overall_confidence(values: list[float]) -> str:
    average = sum(values) / len(values) if values else 0
    return "high" if average >= 80 else "needs_review" if average >= 45 else "unknown"


async def _process_image(image: UploadFile) -> CaptureImageResult:
    started = perf_counter()
    if image.content_type not in ALLOWED_CAPTURE_TYPES:
        raise HTTPException(status_code=415, detail="Upload JPEG, PNG or WebP images")
    data = await image.read(MAX_CAPTURE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail=f"{image.filename or 'Image'} is empty")
    if len(data) > MAX_CAPTURE_BYTES:
        raise HTTPException(status_code=413, detail="Each nutrition-label image must be 10 MB or smaller")
    try:
        source = Image.open(io.BytesIO(data))
        source.verify()
        pil: Any = Image.open(io.BytesIO(data)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=422, detail=f"{image.filename or 'Uploaded file'} is not a valid supported image") from exc

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    upload_id = str(uuid4())
    target = CAPTURE_DIR / f"{upload_id}{ALLOWED_CAPTURE_TYPES[image.content_type]}"
    target.write_bytes(data)
    ocr_started = perf_counter()
    try:
        text = pytesseract.image_to_string(pil, config="--psm 6")
        ocr_data = pytesseract.image_to_data(pil, output_type=pytesseract.Output.DICT, config="--psm 6")
        confidences = [
            float(value)
            for value in ocr_data.get("conf", [])
            if str(value).replace(".", "", 1).isdigit() and float(value) >= 0
        ]
        extraction = parse_nutrition_text(text)
        confidence = _overall_confidence(confidences)
    except (pytesseract.TesseractError, OSError):
        extraction = parse_nutrition_text("")
        confidence = "unknown"
    logger.info(
        "performance operation=capture_image filename=%s upload_ms=%.1f ocr_ms=%.1f total_ms=%.1f",
        image.filename or "image",
        (ocr_started - started) * 1000,
        (perf_counter() - ocr_started) * 1000,
        (perf_counter() - started) * 1000,
    )
    return CaptureImageResult(
        upload_id=upload_id,
        filename=image.filename or "image",
        content_type=image.content_type,
        image_path=target,
        extraction=extraction,
        confidence=confidence,
    )


@router.post("/capture/nutrition-labels", status_code=status.HTTP_202_ACCEPTED)
async def upload_nutrition_labels(images: Annotated[list[UploadFile], File(...)]) -> dict[str, Any]:
    started = perf_counter()
    if not images:
        raise HTTPException(status_code=422, detail="Select at least one image")
    if len(images) > MAX_CAPTURE_IMAGES:
        raise HTTPException(status_code=422, detail=f"Upload no more than {MAX_CAPTURE_IMAGES} images at once")
    processed: list[CaptureImageResult] = []
    try:
        for image in images:
            processed.append(await _process_image(image))
    except HTTPException:
        for item in processed:
            item.image_path.unlink(missing_ok=True)
        raise
    result = merge_extractions(str(uuid4()), processed)
    logger.info(
        "performance operation=capture_to_verification image_count=%d duration_ms=%.1f",
        len(processed),
        (perf_counter() - started) * 1000,
    )
    return capture_response(result)


@router.post("/capture/nutrition-label/review-and-add", response_model=FoodOutput, status_code=status.HTTP_201_CREATED)
def review_and_add(
    payload: NutritionLabelReviewCreate,
    db: DbSession,
    profile_id: str = Query(...),
    day: date = Query(...),
    meal_period: str = Query(...),
    mode: str = Query(default="eaten", pattern="^(eaten|planned)$"),
    servings: float = Query(default=1.0, gt=0, le=100),
) -> Food:
    profile = get_profile_or_404(db, profile_id)
    if payload.barcode:
        existing = local_barcode_food(db, "".join(ch for ch in payload.barcode if ch.isdigit()))
        if existing is not None:
            food = existing
        else:
            food = save_reviewed_nutrition_label(payload, db)
    else:
        food = save_reviewed_nutrition_label(payload, db)

    zone = ZoneInfo(profile.timezone)
    local_dt = datetime.combine(day, time(12, 0), tzinfo=zone)
    if mode == "planned":
        create_planned_entry(
            profile_id,
            PlannedEntryCreate(
                food_id=food.id,
                meal_period=meal_period,  # type: ignore[arg-type]
                planned_for=local_dt,
                servings=servings,
            ),
            db,
        )
    else:
        create_diary_entry(
            profile_id,
            DiaryEntryCreate(
                food_id=food.id,
                meal_period=meal_period,  # type: ignore[arg-type]
                consumed_at=local_dt.astimezone(timezone.utc),
                servings=servings,
            ),
            db,
        )
    return food


@router.get("/capture/{upload_id}/image")
def capture_image_path(upload_id: str) -> Path:
    matching = list(CAPTURE_DIR.glob(f"{upload_id}.*"))
    if not matching:
        raise HTTPException(status_code=404, detail="Capture image not found")
    return matching[0]
