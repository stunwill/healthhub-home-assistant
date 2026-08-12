# HealthHub

HealthHub is a Home Assistant add-on for personal nutrition, calorie planning, activity goals and progress tracking, with a versioned integration to FoodHub.

## Current development release: v0.3.0

HealthHub v0.3.0 adds personal activity and progress tracking to the v0.2 daily nutrition workflow:

- profile-scoped daily food diary
- persistent HealthHub food catalogue
- Australian nutrition-label conventions including kJ, kcal and optional macros
- predictive Quick Add for HealthHub foods
- versioned FoodHub recipe-search adapter with graceful fallback
- manual exercise logging with duration and calories burned
- exercise calories flowing through each profile's configured credit mode
- manual metric weight logging and recent weight history
- functional Progress screen for activity and weight
- phone camera or existing-image nutrition-label capture with mandatory human review

Profiles are data selectors, not secure accounts. Home Assistant is the trust boundary and HealthHub does not implement its own login, passwords, PINs, passkeys or account registration.

## Architecture

HealthHub is a separate application and datastore from FoodHub. It does not read FoodHub's database directly. FoodHub remains the source of truth for shared recipes and scheduled household meals, while HealthHub owns personal profiles, nutrition foods, diary entries, exercise, weight and progress data.

Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic and SQLite.

Frontend: React 19, TypeScript and Vite.

Supported Home Assistant architectures: `aarch64` and `amd64`.

## Data model

v0.3.0 contains five application tables:

- `profiles`, profile identity and nutrition/activity preferences
- `foods`, reusable nutrition and serving definitions
- `diary_entries`, consumed items with immutable nutrition snapshots
- `exercise_entries`, completed activity with user-supplied duration and calories burned
- `weight_entries`, timestamped metric weight measurements

Diary entries keep a snapshot of the food name, serving and nutrition totals at the time they are logged. Editing a food later therefore does not silently alter historical diary totals.

## Exercise calorie credit

Daily remaining calories use the existing profile rule:

`remaining = target - consumed food calories + credited exercise calories`

Credit modes are:

- no exercise credit
- full exercise credit
- percentage exercise credit

HealthHub does not estimate exercise calories in v0.3.0. Users enter calories from a trusted exercise device, application or other source. The configured credit rule then determines how much, if any, is added back to the daily calorie budget.

## Weight and progress

Weight is stored in kilograms using timezone-aware timestamps. The Progress view shows the latest logged weight, optional starting and goal weight context, recent weight history and exercise totals.

HealthHub does not automatically prescribe a calorie target or weight goal and does not provide medical advice.

## Nutrition-label capture

The current workflow remains review-first:

**Take/upload photo → store capture → review values → correct values → save food**

JPEG, PNG and WebP files up to 10 MB are accepted. OCR/AI extraction is not enabled, so extracted values are never fabricated. The review endpoint requires explicit confirmation before captured values can become a food record.

## FoodHub compatibility

HealthHub communicates with FoodHub only through versioned `/api/v1` interfaces. It never reads the FoodHub database.

Predictive Quick Add is ready to include FoodHub recipes when FoodHub exposes `/api/v1/recipes/search`. If that capability is unavailable, FoodHub search returns no results without preventing HealthHub from starting or using its local food catalogue.

FoodHub recipes without authoritative per-serving nutrition are not treated as zero-calorie foods and cannot be silently logged as consumed.

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

Tests:

```bash
cd healthhub
ruff check app tests
mypy app
pytest --cov=app
```

## Home Assistant data and backups

Production data lives under `/data/healthhub`. SQLite uses WAL mode, foreign keys and transactional writes. Nutrition-label captures are temporarily stored under `/data/healthhub/tmp/captures` until reviewed and saved.

The app uses Home Assistant Ingress and the supported structured `addon_config` mapping. It is not exposed to the public internet by default.

## Roadmap

A sensible v0.4.0 scope is weekly food planning and recurrence, including planned versus consumed entries and a functional Week view. Water logging, richer weight charts, barcode/OCR integrations, wearables and smart scales remain later work.
