# HealthHub

HealthHub is a Home Assistant add-on for personal nutrition, calorie planning, activity goals and progress tracking, with a versioned integration to FoodHub.

## Current development release: v0.7.0

HealthHub v0.7.0 extends the v0.6 Food Library with practical food capture, product identity, provenance and authoritative recipe nutrition:

- spreadsheet paste, CSV upload and native XLSX upload through the same validation/preview/import pipeline
- downloadable CSV and XLSX templates using canonical HealthHub columns
- canonical nutrition bases for per serving, per 100 g and per 100 mL nutrition
- local-first barcode lookup with EAN/GTIN validation and reusable product identifiers
- external product search and barcode lookup through a provider abstraction, initially Open Food Facts
- nutrition-label photo capture with local Tesseract OCR inside the HealthHub add-on
- review-first OCR workflow with confidence and nutrition-consistency warnings
- nutrition provenance, provider/source metadata and verification status
- protection against lower-quality imports overwriting verified food data
- FoodHub authoritative per-serving recipe nutrition ingestion through the versioned v1 contract
- immutable consumed diary snapshots, so later food or FoodHub recipe updates do not rewrite historical consumption

Profiles remain data selectors, not secure accounts. Home Assistant is the trust boundary and HealthHub does not implement its own authentication.

## Import foods

Open **Foods → Import & capture foods**. Spreadsheet paste, CSV and XLSX all use the same canonical mapping and validation rules. `name` is required; nutrition fields may be incomplete. Supported nutrition bases are `per_serving`, `per_100g` and `per_100ml`. Invalid negative or malformed values are rejected, while suspicious nutrient relationships are shown as review warnings.

CSV supports UTF-8 and UTF-8 BOM. Common comma, semicolon, tab and pipe delimiters are detected where practical. XLSX workbooks detect non-empty worksheets and use the selected worksheet for preview and import. Uploads are limited to 5 MB and 10,000 rows.

## Barcode and product lookup

Barcode lookup is local-first. HealthHub checks `food_identifiers` before any external request. Existing local products are reused rather than duplicated. When no local match exists, the configured product provider may supply a preview candidate. External data never saves automatically and must be reviewed first.

The initial provider is Open Food Facts behind the `ProductLookupProvider` abstraction. Provider failure does not block manual food creation, local search, file import or previously saved foods.

## Nutrition-label capture and privacy

JPEG, PNG and WebP images up to 10 MB are accepted. OCR is performed locally with Tesseract in the HealthHub container. Nutrition-label images are not sent to a third-party OCR service by HealthHub. OCR text is normalised for common label and recognition issues and produces field confidence plus consistency warnings.

The workflow is:

**Image → local OCR → parse → normalise → confidence/warnings → user review → validation → duplicate check → save**

OCR values are never treated as packaging-confirmed until the user has reviewed them. Reviewed records use packaging-label provenance and retain verification metadata.

## FoodHub compatibility

HealthHub communicates with FoodHub only through versioned `/api/v1` interfaces and never reads the FoodHub database.

The current FoodHub v1 contract can expose authoritative per-serving recipe nutrition. HealthHub can consume that nutrition and maintain a linked Food Library record for future selections. Consumed diary entries continue to snapshot nutrition, so later FoodHub recipe changes affect future selections only.

The current FoodHub v1 contract does **not** expose recipe ingredient quantities. HealthHub therefore does not pretend ingredient-level mapping/calculation is authoritative yet. The v0.7 schema includes the mapping foundation, but ingredient-level calculation remains unavailable until FoodHub exposes the required versioned ingredient data.

## Architecture and data safety

HealthHub keeps its own SQLite datastore and Alembic migrations. v0.7 adds product identifiers, canonical nutrition/provenance fields, FoodHub recipe links and ingredient-mapping foundations without resetting existing data. Existing foods, composites, profile preferences, import history, diary snapshots, plans, exercise, weight and hydration records are preserved.

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

## Roadmap

Future work includes meal-photo calorie estimation, improved automatic food-image recognition, wearable integration, smart-scale integration, additional product providers, nutrition data refresh workflows, richer ingredient/unit conversion, recipe serving/yield intelligence, Food Library export/backup and an optional household-shared custom product catalogue.
