# HealthHub Roadmap

## v0.8.1 - Daily Diary Image & Barcode Capture

Status: Released

### Features
- [x] Daily Diary Quick Add entry points for Search, Scan Barcode, Take Photo and Upload Photo(s).
- [x] Multi-image nutrition capture with local OCR and human verification.
- [x] Diary-aware barcode lookup with local-first reuse and external product review.
- [x] Food Library, CSV/XLSX import, barcode/product lookup and FoodHub authoritative recipe nutrition integration from earlier releases.

### UX
- [x] Preserve selected profile, date, meal section and planned/eaten state through capture workflows.
- [x] Mobile-friendly capture controls and image previews.

### Testing
- [x] Backend regression coverage for capture, barcode, import, diary isolation and temporary-file cleanup.

## v0.9.0 - Saved Meal Management & Nutrition Targets

Status: Planned

### Features
- [ ] Expand reusable saved-meal management beyond the v0.8 foundation.
- [ ] Add optional profile-level macro targets and clearer nutrition target tracking.
- [ ] Improve FoodHub recipe and serving workflows while preserving FoodHub as the recipe authority.

### UX
- [ ] Make saved meals easier to create, edit, reuse and plan from Daily Diary and weekly planning views.
- [ ] Present calorie and optional macro targets consistently across daily and weekly views.

### Testing
- [ ] Preserve existing food library, import, barcode, OCR, mobile, diary, planning and FoodHub integration coverage.
- [ ] Add regression coverage for saved-meal editing and nutrition target calculations.

## Future

- Wearable and activity-provider integrations.
- Smart-scale integrations and richer progress trends.
- Meal-photo calorie estimation only when confidence and human-review safeguards are appropriate.
- Deeper FoodHub ingredient-level integration if the versioned FoodHub API exposes authoritative ingredient quantities.
- Additional Home Assistant entities, automations and dashboard integrations where they add practical value.
