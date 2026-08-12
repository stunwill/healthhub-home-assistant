# Changelog

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
