# HealthHub

HealthHub is a Home Assistant add-on for personal nutrition, calorie planning, activity goals and progress tracking, with a versioned integration to FoodHub.

## Current development release: v0.4.0

HealthHub v0.4.0 adds weekly food planning and recurrence to the existing nutrition, exercise and progress workflows:

- profile-scoped daily food diary
- persistent HealthHub food catalogue
- predictive Quick Add for HealthHub foods
- manual exercise and metric weight logging
- exercise-credit-aware daily calorie budgets
- functional Progress view
- planned food entries with nutrition snapshots
- functional Week view with planned versus consumed totals
- consume, skip and remove planning actions
- daily, weekday and weekly recurrence rules
- phone camera or existing-image nutrition-label capture with mandatory human review

Profiles are data selectors, not secure accounts. Home Assistant is the trust boundary and HealthHub does not implement its own login, passwords, PINs, passkeys or account registration.

## Architecture

HealthHub is a separate application and datastore from FoodHub. It does not read FoodHub's database directly. FoodHub remains the source of truth for shared recipes and scheduled household meals, while HealthHub owns personal profiles, nutrition foods, diary entries, exercise, weight, plans, recurrence and progress data.

Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic and SQLite.

Frontend: React 19, TypeScript and Vite.

Supported Home Assistant architectures: `aarch64` and `amd64`.

## Data model

v0.4.0 contains seven application tables:

- `profiles`, profile identity and nutrition/activity preferences
- `foods`, reusable nutrition and serving definitions
- `diary_entries`, consumed items with immutable nutrition snapshots
- `exercise_entries`, completed activity with user-supplied duration and calories burned
- `weight_entries`, timestamped metric weight measurements
- `planned_entries`, profile-specific planned food snapshots and status
- `recurrence_rules`, simple daily, weekday and weekly planning rules

Consumed diary entries and planned entries both snapshot nutrition so later food edits do not silently rewrite historical or already-planned values.

## Planning and recurrence

The Week view shows seven days of planned and consumed calories and lets a user add HealthHub foods to a specific date, time and meal period. Planned items can be marked consumed or skipped. Marking an item consumed creates a real diary entry from the planned nutrition snapshot.

Recurrence supports daily, weekdays and weekly rules. Rules materialise planned entries for an eight-week horizon. Recurrence never marks food as consumed automatically.

FoodHub scheduled household dinners and HealthHub personal plans remain separate sources of truth. HealthHub does not write directly to FoodHub schedules.

## Exercise calorie credit

Daily remaining calories use:

`remaining = target - consumed food calories + credited exercise calories`

Credit modes are no credit, full credit and percentage credit. HealthHub does not estimate exercise calories. Users enter calories from a trusted device, application or other source.

## Nutrition-label capture

The current workflow remains review-first:

**Take/upload photo → store capture → review values → correct values → save food**

JPEG, PNG and WebP files up to 10 MB are accepted. OCR/AI extraction is not enabled, so extracted values are never fabricated.

## FoodHub compatibility

HealthHub communicates with FoodHub only through versioned `/api/v1` interfaces and never reads the FoodHub database.

FoodHub recipes without authoritative per-serving nutrition are not treated as zero-calorie foods and cannot be silently logged or planned as consumed nutrition.

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

## Home Assistant data and backups

Production data lives under `/data/healthhub`. SQLite uses WAL mode, foreign keys and transactional writes. The app uses Home Assistant Ingress on port 8098 and is not exposed to the public internet by default.

## Roadmap

A sensible next scope is hydration logging and richer progress visualisation. Drag-and-drop planning, unscheduled meal trays, barcode/OCR integrations, wearables and smart-scale imports remain later work.
