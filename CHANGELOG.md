# Changelog

## 0.4.0 - Planning & Recurrence

### Added

- Added profile-scoped planned food entries with immutable nutrition snapshots, meal period, servings and timezone-aware planned times.
- Added a functional Week view with previous/next week navigation, daily planned-versus-consumed calorie totals and planned item status.
- Added actions to mark a planned item consumed, skip it, or remove an unconsumed plan.
- Marking a planned item consumed creates a real diary entry using the planned nutrition snapshot, it does not silently alter the underlying food definition.
- Added simple recurrence rules for daily, weekdays and weekly patterns, materialised for an eight-week planning horizon.
- Added weekly plan summary and recurrence management endpoints under `/api/v1`.
- Added Alembic migration `0004_planning_recurrence` and backend tests covering plan, consume, skip, recurrence, weekly totals, validation and migrations.

### Behaviour and boundaries

- Planning remains profile-specific HealthHub data and does not modify FoodHub schedules.
- FoodHub recipes are not treated as consumable HealthHub nutrition unless authoritative per-serving nutrition is available through the versioned integration contract.
- Recurrence creates planned entries only. It never marks food as consumed automatically.
- Home Assistant remains the trust boundary, no HealthHub authentication has been added.

### Deferred

- Drag-and-drop planning and an unscheduled meal tray.
- Water logging.
- Richer weight charts and trend analytics.
- Barcode lookup, functional OCR/AI extraction, wearables and smart scales.

## 0.3.0 - Exercise, Weight & Progress

### Added

- Added profile-scoped manual exercise entries with activity name, duration, calories burned, timezone-aware completion time and optional notes.
- Added profile-scoped weight entries with metric kilograms and timezone-aware measurement time.
- Added exercise-aware daily calorie summaries. Completed exercise calories now flow through the existing no-credit, full-credit or percentage-credit profile setting before affecting remaining calories.
- Added a functional Progress screen for exercise logging, weight logging, recent weight history, goal context and exercise totals.
- Added Quick Add shortcuts for Exercise and Weight that open the Progress workflow.
- Added Alembic migration `0003_exercise_weight` and API/integration tests for exercise-credit behaviour, weight history, progress summaries and timestamp validation.

### Safety and scope

- HealthHub does not estimate exercise calories in v0.3.0. Users enter values from a trusted device or source.
- Weight goals remain user-configured values. HealthHub does not prescribe a target or provide medical advice.
- Home Assistant remains the trust boundary; no separate authentication has been introduced.

### Deferred

- Weekly meal planning, planned food entries and recurrence.
- Water logging.
- Weight charts and advanced trend analytics.
- Barcode lookup, functional OCR/AI extraction, wearables and smart scales.

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

- Home Assistant app configuration uses the supported structured `addon_config` mapping.
- Container/runtime version handling preserves the build version rather than resetting it from an unavailable runtime build argument.

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
