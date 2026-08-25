# HealthHub

HealthHub is a Home Assistant add-on for personal nutrition, calorie planning, activity goals and progress tracking, with a versioned integration to FoodHub.

## Current development release: v0.8.0

HealthHub v0.8.0 turns the Food Library and capture foundation into an everyday diary and planning workflow:

- selected-date Daily Diary with Breakfast, Morning Snack, Lunch, Afternoon Snack, Dinner, Evening Snack and Drinks sections
- clear Daily Goal, Eaten, Planned and Remaining-after-planned calorie budget
- protein, carbohydrates, fat and sugar daily totals
- planned-versus-eaten state with one-action Mark eaten
- edit serving quantity and meal placement while preserving nutrition snapshots
- copy individual foods, meal sections and entire days, with copied items created as Planned
- reusable saved-meal definitions and planning APIs
- profile-aware favourites, frequent and recent food ranking in Quick Add
- local-first predictive search that displays HealthHub results without waiting for FoodHub
- cancellable stale searches and separately merged FoodHub recipe results
- authoritative FoodHub recipe planning with immutable HealthHub nutrition snapshots
- responsive Add to Plan feedback, duplicate-click protection and immediate local reconciliation
- weekly-summary and recurrence query optimisation for Home Assistant-class hardware

Profiles remain data selectors, not secure accounts. Home Assistant is the trust boundary and HealthHub does not implement its own authentication.

## Daily diary and calorie budget

The Today view can navigate to previous or future dates. Planned foods are not counted as consumed. The primary budget is:

`remaining after planned = daily target - eaten calories - planned calories`

Planned entries can be marked eaten, which creates a consumed diary snapshot from the nutrition values already stored on the plan. Later edits to the Food Library or FoodHub recipe do not rewrite that historical nutrition.

Future copies of foods, meals and complete days are created as Planned by default.

## Quick Add and search

Quick Add ranks profile-specific favourites, frequent foods and recent foods ahead of general Food Library results. When the user types a query, HealthHub local search returns first. FoodHub recipe lookup is a separate cancellable request and is merged into the visible results when available.

A slow or unavailable FoodHub service therefore does not block local foods.

## Weekly planning and responsiveness

The Week planner provides immediate `Adding…` feedback and disables the in-flight submission to prevent duplicate clicks. One-off additions use the newly created planned-entry response to update the visible week rather than blocking on a complete week reload.

The weekly summary now loads the requested week's planned entries in one range query and consumed diary entries in one range query, replacing the previous per-day query loop. Recurrence materialisation fetches existing occurrences once for the materialisation range instead of performing one existence query for every candidate date.

## Reusable meals

v0.8 adds profile-scoped `saved_meals` and `saved_meal_items`. A saved meal is a reusable definition of Food Library items and servings. Planning a saved meal creates independent planned-entry nutrition snapshots, so later edits to the saved meal do not silently change existing plans.

## FoodHub compatibility

HealthHub communicates with FoodHub only through versioned `/api/v1` interfaces and never reads the FoodHub database.

FoodHub remains authoritative for recipe identity and current recipe nutrition. When a FoodHub recipe is selected for planning or logging, HealthHub synchronises an authoritative local recipe representation and snapshots the selected nutrition into the diary or plan. Later FoodHub changes apply to future selections only.

Repeated v0.8 FoodHub searches use a pooled HTTP client with keep-alive and application shutdown cleanup. Optional FoodHub failure does not block local HealthHub search or planning.

## Import, barcode and nutrition-label capture

The v0.7 capabilities remain available:

- spreadsheet paste, CSV and XLSX import through validation and duplicate preview
- local-first barcode identity and external product lookup
- local Tesseract OCR for JPEG, PNG and WebP nutrition labels
- mandatory human review before OCR-derived nutrition is saved
- nutrition provenance and source-precedence protection

## Architecture and data safety

HealthHub keeps its own SQLite datastore and Alembic migrations. SQLite uses WAL mode and existing profile/date indexes. v0.8 adds migration `0008_saved_meals`; it does not reset or recreate the database.

Production data lives under `/data/healthhub`. Home Assistant Ingress remains the default access path.

## Development

Backend:

```bash
cd healthhub
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export HEALTHHUB_DATABASE_URL=sqlite:///./healthhub-dev.db
alembic upgrade head
uvicorn app.start:app --reload --port 8098
```

Frontend:

```bash
cd healthhub/frontend
npm install
npm run dev
```

Full preflight:

```bash
./scripts/preflight.sh
```

## Roadmap

A sensible next release is exercise and progress integration around the new daily calorie budget, followed by richer saved-meal management, optional macro targets and deeper FoodHub recipe/serving workflows. Wearables, smart-scale integrations and meal-photo calorie estimation remain later work.
