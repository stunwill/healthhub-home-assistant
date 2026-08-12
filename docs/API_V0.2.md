# HealthHub API v1 additions in v0.2.0

## Foods

- `GET /api/v1/foods`
- `POST /api/v1/foods`
- `GET /api/v1/foods/{food_id}`
- `PATCH /api/v1/foods/{food_id}`
- `POST /api/v1/foods/{food_id}/archive`

## Diary

- `GET /api/v1/profiles/{profile_id}/diary?day=YYYY-MM-DD`
- `POST /api/v1/profiles/{profile_id}/diary`
- `DELETE /api/v1/profiles/{profile_id}/diary/{entry_id}`
- `GET /api/v1/profiles/{profile_id}/daily-summary?day=YYYY-MM-DD`

## Quick Add

- `GET /api/v1/quick-add/search?q=...`

Local HealthHub foods are authoritative. FoodHub recipe results are included only when the versioned FoodHub recipe search endpoint is available. Missing or incomplete FoodHub nutrition is returned as unavailable, not zero.

## Nutrition-label capture

- `POST /api/v1/capture/nutrition-label`, multipart image upload
- `POST /api/v1/capture/nutrition-label/review`, reviewed values saved as a HealthHub food

Accepted images are JPEG, PNG and WebP up to 10 MB. OCR is not enabled in v0.2.0. The capture response contains no fabricated extraction values and the review endpoint requires `reviewed: true`.
