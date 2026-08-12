# HealthHub v0.1.0 Implementation Plan

## 1. FoodHub repository assessment

FoodHub currently exists as `stunwill/dinnerhub-home-assistant` and uses FastAPI, SQLAlchemy/SQLite, React/Vite/TypeScript, Home Assistant Ingress, `/data/dinnerhub` persistence, Ruff/pytest, GitHub Actions and `aarch64`/`amd64` add-on builds. The current technical namespace and stable install identifier remain `dinnerhub` for compatibility.

## 2. HealthHub repository

HealthHub is a separate public repository: `stunwill/healthhub-home-assistant`.

## 3. Technology stack

Reuse the FoodHub ecosystem where suitable: Python 3.12, FastAPI, SQLAlchemy 2, SQLite with WAL, Alembic migrations, React 19, TypeScript and Vite. This reduces operational and maintenance complexity without coupling the applications or their datastores.

## 4. FoodHub rename and compatibility

FoodHub is a user-facing rename only in the compatibility release. The `dinnerhub` add-on slug, persistent paths, existing HA entities, repository name and other stable identifiers remain until a dedicated migration is approved.

## 5. HealthHub structure

- `healthhub/app`: API, domain services, persistence and integrations
- `healthhub/migrations`: ordered schema migrations
- `healthhub/frontend`: responsive React application
- `healthhub/tests`: backend, API and migration tests
- `docs`: architecture and release documentation
- `.github/workflows`: CI

## 6. v0.1 database schema

Only the `profiles` table is introduced. It includes stable UUID identifiers, profile display fields, optional height and weight goal fields, calorie/exercise/hydration targets, exercise-credit configuration, nutrition display mode, timezone, measurement units, archive state, and created/updated timestamps. Future diary, food, exercise and progress tables are deliberately deferred.

## 7. API endpoints

- `GET /api/v1/health`
- `GET /api/v1/version`
- `GET/POST /api/v1/profiles`
- `GET/PATCH /api/v1/profiles/{profile_id}`
- `POST /api/v1/profiles/{profile_id}/archive`
- `GET/PUT /api/v1/active-profile`
- `POST /api/v1/calorie-budget`
- `GET /api/v1/integrations/foodhub`
- `POST /api/v1/capture/nutrition-label` as a non-OCR architectural contract

## 8. UI screens and components

Today and Settings are the initial functional navigation surfaces. The shell includes a profile switcher, target cards, visible empty states and a prominent Quick Add entry point. Week and Progress remain honest placeholders. Predictive Quick Add exposes the future search contract without fabricated results.

## 9. FoodHub boundary

HealthHub accesses FoodHub only through `/api/v1`. A typed adapter uses short timeouts and returns explicit unavailable/incompatible states. HealthHub startup and profile functions remain independent when FoodHub is offline.

## 10. Testing strategy

Unit-test calorie-credit rules and rounding, API-test profile CRUD/validation/active selection, migration-test the initial schema, component-test profile switching/settings once the frontend test harness is available, and add an end-to-end Home Assistant smoke test when container tooling is available.

## 11. Security and persistence

Home Assistant Ingress is the trust boundary. HealthHub adds no passwords, registration, PINs, passkeys or per-profile security. Production data remains under `/data/healthhub`; SQLite uses WAL and foreign keys. Request bodies containing future diary information should not be logged by default.

## 12. Risks and deviations

The approved architecture is followed. One deliberate implementation detail is that HealthHub adopts Alembic immediately even though current FoodHub still uses runtime `create_all()`. Retrofitting FoodHub migrations is out of scope for the compatibility change. Active-profile storage in v0.1 is installation-local convenience state, not authentication.

## 13. Proposed commit sequence

1. Add-on and dependency foundation.
2. Database, migration and profile model.
3. API, validation and calorie-budget domain service.
4. FoodHub adapter and capture extension contracts.
5. Responsive frontend shell and profile/settings interactions.
6. Tests and CI.
7. Documentation and changelog.
8. Validation fixes and draft pull request.
