# HealthHub

HealthHub is a Home Assistant add-on for personal nutrition, calorie planning, activity goals and progress tracking, with a versioned integration to FoodHub.

## Current development release: v0.2.0

HealthHub v0.2.0 moves the foundation into a usable daily nutrition workflow:

- profile-scoped daily food diary
- persistent HealthHub food catalogue
- Australian nutrition-label conventions including kJ, kcal and optional macros
- predictive Quick Add for HealthHub foods
- versioned FoodHub recipe-search adapter with graceful fallback
- daily consumed, target and remaining calorie totals
- protein, carbohydrate and fat daily aggregation
- phone camera or existing-image nutrition-label capture
- mandatory human review before captured label values can be saved
- no OCR or AI extraction pretending to know label values

Profiles are data selectors, not secure accounts. Home Assistant is the trust boundary and HealthHub does not implement its own login, passwords, PINs, passkeys or account registration.

## Architecture

HealthHub is a separate application and datastore from FoodHub. It does not read FoodHub's database directly. FoodHub remains the source of truth for shared recipes and scheduled household meals, while HealthHub owns personal profiles, foods created specifically for nutrition tracking, diary entries, goals and future exercise/progress records.

Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic and SQLite.

Frontend: React 19, TypeScript and Vite.

Supported Home Assistant architectures: `aarch64` and `amd64`.

## Data model

v0.2.0 contains three application tables:

- `profiles`, profile identity and nutrition preferences
- `foods`, reusable nutrition/serving definitions
- `diary_entries`, consumed items with nutrition snapshots

Diary entries keep a snapshot of the food name, serving and nutrition totals at the time they are logged. Editing a food later therefore does not silently alter historical diary totals.

## Nutrition-label capture

The v0.2.0 workflow is deliberately review-first:

**Take/upload photo → store capture → review values → correct values → save food**

JPEG, PNG and WebP files up to 10 MB are accepted. OCR/AI extraction is not enabled in v0.2.0, so extracted values are never fabricated. The review endpoint requires explicit confirmation before the captured values can become a food record.

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
uvicorn app.main:app --reload --port 8098
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

The add-on uses Home Assistant Ingress and the current `app_config` mapping. It is not exposed to the public internet by default.

## Roadmap

A sensible v0.3.0 scope is exercise and weight logging plus progress foundations, including exercise calorie credits feeding the real daily budget, while leaving wearables, recurrence, weekly planning and advanced analytics for later releases.
