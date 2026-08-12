# Changelog

## 0.2.0 - Daily Diary & Food Core

### Added

- Added a persistent HealthHub food catalogue with stable IDs, foods/drinks, brand, serving size, Australian energy in kJ, calories and optional protein, carbohydrate and fat values.
- Added profile-scoped consumed diary entries with meal periods, timezone-aware timestamps and immutable nutrition snapshots so later food edits do not rewrite diary history.
- Added daily calorie and macro summaries using the profile calorie target and existing exercise-credit calculation domain service.
- Added predictive Quick Add search across HealthHub foods, with a versioned FoodHub recipe-search adapter that degrades cleanly until the FoodHub search capability is available.
- Added a functional mobile-first Today diary with consumed, remaining and target calories, protein totals, entry removal and Quick Add logging.
- Added manual food creation using Australian nutrition-label conventions.
- Added phone camera/existing-image nutrition-label upload for JPEG, PNG and WebP files up to 10 MB.
- Added a mandatory review endpoint for nutrition-label values before a captured label can become a saved food.
- Added v0.2 Alembic migration coverage and API tests for food search, diary logging, daily summaries, archiving and nutrition-label review.

### Changed

- HealthHub now uses the current Home Assistant `app_config` mapping instead of the legacy `addon_config` map type.
- Container/runtime version handling now preserves the build version rather than resetting it from an unavailable runtime build argument.

### Deliberately deferred

- OCR/AI nutrition-label extraction. v0.2 stores the image and requires manual review/entry; it does not fabricate extracted values.
- Barcode lookup and external commercial nutrition APIs.
- FoodHub recipe logging where authoritative per-serving nutrition is unavailable.
- Exercise diary, weight tracking, weekly planning, recurrence, progress charts and wearable imports.

## 0.1.0 - Foundation & Profiles

### Added

- Home Assistant add-on configuration with Ingress, metric/Australian defaults and `aarch64`/`amd64` support.
- FastAPI `/api/v1` foundation with health, version, profiles, active-profile selection, calorie-budget calculation and FoodHub integration status.
- SQLite persistence under `/data/healthhub` with WAL, foreign keys and Alembic migrations from the first release.
- Profile data model covering display name, optional body measurements and goal date, calorie target, exercise target, hydration target, exercise-credit mode, nutrition display mode, timezone and metric units.
- Profile creation, update, archive and switching support without introducing module authentication.
- Reusable calorie-budget domain calculation supporting no, full and percentage exercise credit with half-up whole-kcal rounding.
- Typed FoodHub v1 adapter with short timeouts and graceful degraded-state behaviour.
- Mobile-first React shell with Today, Week, Progress, Settings and Quick Add entry point.
- Honest placeholders for deferred diary, weekly planning, progress and capture features.
- Nutrition-label capture contract that requires review but deliberately performs no OCR in v0.1.0.
- Unit, API and migration test foundations.

### Compatibility

- HealthHub owns a separate datastore and never queries FoodHub's database directly.
- Home Assistant remains the sole authentication boundary.
- No real personal health data is seeded.
