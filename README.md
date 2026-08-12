# HealthHub

HealthHub is a Home Assistant add-on for personal nutrition, calorie planning, activity goals and progress tracking, with a versioned integration to FoodHub.

## v0.1.0 scope

This first development release establishes:

- Home Assistant add-on packaging and Ingress access
- FastAPI backend and React/TypeScript frontend foundation
- SQLite persistence under `/data/healthhub`
- schema migrations from the first release
- profile creation, editing, archiving and active-profile selection
- calorie, exercise, hydration and nutrition-display preferences
- reusable calorie-budget calculation
- FoodHub v1 connectivity adapter with graceful degradation
- Quick Add and nutrition-label capture extension points without fake business logic
- mobile-first Today shell and Settings foundation

Profiles are data selectors, not secure accounts. Home Assistant is the trust boundary and HealthHub does not implement its own login, passwords, PINs, passkeys or account registration.

## Architecture

HealthHub is a separate application and datastore from FoodHub. It does not read FoodHub's database directly. FoodHub remains the source of truth for shared recipes and scheduled household meals, while HealthHub owns personal profiles and future diary, goals, exercise and progress records.

Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic, SQLite.

Frontend: React 19, TypeScript and Vite.

Supported Home Assistant architectures match FoodHub: `aarch64` and `amd64`.

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

## Data and backups

Production data lives under `/data/healthhub`. SQLite uses WAL mode, foreign keys and transactional writes. HealthHub data is therefore included with Home Assistant add-on data backups. No real personal health information is seeded by default.

## FoodHub compatibility

HealthHub expects the versioned FoodHub `/api/v1` contract introduced by the FoodHub compatibility foundation. FoodHub being unavailable does not prevent HealthHub startup.

## Roadmap

v0.2.0 is expected to introduce the daily diary and Australian food core, including real predictive Quick Add and reviewed nutrition-label capture, while continuing to keep FoodHub integration read-only and versioned.
