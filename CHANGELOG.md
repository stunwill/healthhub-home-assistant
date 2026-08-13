# Changelog

## 0.5.0 - Hydration & Progress Visualisation

### Added

- Added profile-scoped water logging with millilitre amounts, timezone-aware timestamps, history and delete support.
- Added hydration progress to Today and Progress using the profile's optional hydration target.
- Added Quick Add access to the Water workflow and common 250 mL, 500 mL and 750 mL shortcuts.
- Added sugar as an optional nutrition value on HealthHub foods, consumed diary snapshots and planned-entry snapshots.
- Added a true multi-select nutrition-display preference supporting any combination of Calories, Protein, Carbohydrates, Fat and Sugar, including Calories + Sugar only.
- Added improved Progress visualisation for the last seven days of exercise against the weekly target and a lightweight weight trend chart.
- Added Alembic migration `0005_hydration_nutrition_fields` and backend coverage for hydration, sugar snapshots, nutrition preferences and migrations.

### Changed

- Profile onboarding no longer asks for timezone or measurement units. HealthHub uses `Australia/Melbourne` and metric units automatically.
- Existing Simple, Balanced and Detailed nutrition presets are migrated to equivalent explicit nutrition-field selections.
- Profile Settings now lets an existing profile update its nutrition-display fields and optional hydration target.
- Progress now compares the weekly exercise target with the actual last seven days rather than comparing a 90-day total with one weekly target.

### Data / migration impact

- Adds the `water_entries` table.
- Adds `nutrition_display_fields` to profiles.
- Adds nullable `sugar_g` columns to foods, diary entries and planned entries.
- Existing profile nutrition-display settings are preserved through migration mapping.
- Existing food, diary, planning, exercise and weight data is preserved.

### Safety and scope

- HealthHub does not prescribe hydration targets, calorie targets, weight goals or exercise calories.
- Hydration targets remain optional and user-configured.
- OCR/AI label extraction, barcode lookup, wearable imports and smart-scale integration remain deferred.

## 0.4.2 - Profile Onboarding Fix

### Fixed

- Fixed the first-run `Open settings` action appearing to do nothing when no profiles exist. The zero-profile render path previously always displayed the same empty-state card regardless of the selected navigation view.
- Added a functional first-profile form for display name, calorie target, weekly exercise target, exercise-credit mode, nutrition display mode, timezone and metric units.
- Newly created profiles are automatically selected as the active profile and HealthHub opens the Today view after creation.
- Disabled Week, Progress and the profile selector until a profile exists so first-run navigation cannot lead to misleading empty states.

## 0.4.1 - Home Assistant Ingress Proxy Fix

### Fixed

- Removed HealthHub's custom runtime IP allow-list from the Home Assistant Ingress path. Uvicorn honours trusted proxy headers, so legitimate Ingress requests can present the browser's forwarded LAN address rather than the Supervisor proxy address. The old allow-list could therefore reject valid Home Assistant Web UI requests.
- Home Assistant remains the trust boundary. HealthHub still does not publish its internal port externally by default and no application authentication has been added.
- Added regression coverage ensuring the production runtime does not enable the conflicting custom Ingress IP filter and that a forwarded LAN client can reach the HealthHub health endpoint.

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

- Barcode lookup.
- OCR or AI extraction.
- Meal-photo calorie estimation.
- External commercial nutrition APIs.
- Exercise diary, weight charts and wearable integrations.

## 0.1.0 - Foundation & Profiles

### Added

- Initial Home Assistant add-on foundation with FastAPI, React, SQLite and Ingress support.
- Profile creation, editing, archiving and active-profile selection.
- Persisted nutrition and activity targets and preferences.
- Versioned `/api/v1` API and FoodHub integration adapter.
- Initial Alembic migration and migration tests.
- Reusable exercise-credit calorie-budget domain service.
- Quick Add and nutrition-label capture extension points.
