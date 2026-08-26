# Changelog

## 0.8.1 - Daily Diary Image & Barcode Capture

### Added

- Added explicit Search, Scan Barcode, Take Photo and Upload Photo(s) entry points to Daily Diary Quick Add.
- Added multi-image nutrition capture sessions for up to eight JPEG, PNG or WebP images belonging to one food/product capture.
- Added per-image local Tesseract OCR with deterministic field merging, source-image tracking and conflict warnings.
- Added image previews, remove/clear controls and staged capture progress feedback.
- Added mandatory inline human verification before OCR-derived nutrition is saved.
- Added direct Save & Add to the selected profile, date and meal section without requiring the user to search for the captured food again.
- Added diary-aware barcode camera/manual lookup so barcode workflows retain the selected meal/date context.
- Added performance logging for image upload/OCR and total capture-to-verification duration.

### Changed

- Future/planned image and barcode captures create Planned entries rather than being counted as consumed.
- Local barcode matches are reused instead of creating duplicate food records. External barcode matches still require review before save/use.
- Multi-image fields prefer higher-confidence OCR values and surface equal-confidence conflicts rather than silently overwriting them.
- Temporary source images are cleaned up after a verified capture is saved.
- Quick Add image and barcode workflows remain usable without FoodHub. Local OCR does not depend on an external product service.

### Mobile and privacy

- Camera capture uses the device-facing browser file/camera workflow and remains inside the Home Assistant Ingress Daily Diary experience.
- Mobile capture controls stack at narrow widths and the Quick Add sheet suppresses horizontal overflow.
- Nutrition-label OCR remains local to HealthHub. Captured source images are not sent to a third-party OCR service.

### Migration and compatibility

- v0.8.1 requires no database migration.
- Existing v0.8 diary, planning, saved meal, Food Library, product, OCR and historical nutrition snapshot data are preserved.

## 0.8.0 - Daily Diary, Meal Planning & Planner Responsiveness

### Added

- Added a selected-date Daily Diary with Breakfast, Morning Snack, Lunch, Afternoon Snack, Dinner, Evening Snack and Drinks sections.
- Added explicit Daily Goal, Eaten, Planned and Remaining-after-planned calorie totals plus protein, carbohydrate, fat and sugar totals.
- Added planned-entry editing, Mark eaten, individual copy, meal copy and whole-day copy workflows. Copied historical food is created as Planned and retains its nutrition snapshot.
- Added profile-scoped reusable saved meals and saved meal items with independent planned-entry snapshots.
- Added local-first Quick Add suggestions ranked by profile favourites, use frequency and recency.
- Added independent FoodHub recipe search and authoritative FoodHub recipe planning.
- Added lightweight performance logging for local predictive search and FoodHub search.

### Planner responsiveness

- Add to Plan now enters an immediate `Adding…` state, disables duplicate submission and restores the controls after success or failure.
- One-off planned foods use the POST response to update the visible week immediately instead of blocking on a full week reload.
- Weekly summary data is loaded using one planned-entry range query and one consumed-entry range query instead of querying each of seven days separately.
- Recurrence materialisation loads all existing occurrences for the horizon in one query and performs in-memory duplicate checking rather than an existence query for every candidate date.
- Predictive search cancels stale requests. Local HealthHub results are displayed before the separately requested FoodHub results.
- Repeated FoodHub requests use a pooled HTTP client with keep-alive and application shutdown cleanup.

### Changed

- Expanded meal-period values to support separate morning, afternoon and evening snack sections while retaining the legacy `snack` value for existing records.
- Planned serving changes rescale the stored nutrition snapshot rather than re-reading potentially changed Food Library nutrition.
- Consumed diary entries can be edited for serving quantity and meal placement while preserving snapshot semantics.
- FoodHub-linked recipes are suppressed from external search after a local linked representation exists, reducing duplicate results.

### Migration and compatibility

- Added Alembic migration `0008_saved_meals` for `saved_meals` and `saved_meal_items`.
- Existing v0.7 Food Library records, barcode/product data, OCR metadata, FoodHub links, diary snapshots, planned entries, recurrence rules, exercise, weight and hydration data are preserved.
- Home Assistant remains the trust boundary; no application authentication layer is added.

## 0.7.0 - Food Capture, Product Lookup & Recipe Nutrition

### Added

- Added CSV and native XLSX upload through the existing Food Library validation, mapping, duplicate-preview and import-batch pipeline.
- Added downloadable CSV/XLSX templates and canonical nutrition basis support for per serving, per 100 g and per 100 mL values.
- Added barcode identifiers, local-first barcode lookup, checksum validation and unknown-barcode create flow.
- Added a provider abstraction for external product lookup with Open Food Facts as the initial provider.
- Added local nutrition-label OCR using Tesseract inside the HealthHub add-on, with normalisation, confidence, review warnings and mandatory human confirmation.
- Added food provenance fields for provider/source identifiers, verification, OCR confidence, source URL and product image references.
- Added source-precedence protection so lower-quality imports do not silently overwrite higher-quality verified nutrition.
- Added authoritative FoodHub per-serving recipe nutrition ingestion using the current versioned FoodHub v1 contract.
- Added FoodHub recipe-link and ingredient-mapping foundation tables while keeping historical diary nutrition immutable.

### Changed

- Food Library search can match category and barcode as well as name and brand.
- Per-100 g products can retain canonical nutrition while user servings scale diary nutrition without rewriting the product record.
- CI now runs pull-request checks for PRs targeting `main` and push checks for `main`, avoiding duplicate feature-branch suites.

### Privacy and offline behaviour

- Nutrition-label OCR runs locally. HealthHub does not send captured label images to a third-party OCR service.
- External product provider failure does not block local foods, manual entry, file import, barcode local lookup or previously stored products.

### FoodHub limitation

- FoodHub currently exposes authoritative per-serving recipe nutrition through v1 but does not expose ingredient quantities through the versioned contract. Ingredient-level mapping/calculation remains unavailable until FoodHub supplies that data. HealthHub does not scrape or invent it.

### Migration and compatibility

- Added Alembic migration `0007_food_capture_products` without resetting existing data.
- Existing v0.6 foods, composites, profile preferences, import history, diary snapshots, planned entries, exercise, weight and hydration data are preserved.

## 0.6.0 - Food Library & Spreadsheet Import

### Added

- Extended the shared HealthHub food catalogue with categories, serving units, nutrition quality/source status and additional micronutrients.
- Added idempotent initial foods for Stu, with estimated and packaging-confirmed values clearly distinguished.
- Added reusable composite foods with component quantities and calculated nutrition.
- Added profile-scoped food preferences, recent-use tracking, favourites and personal defaults without changing shared food records.
- Added TSV spreadsheet paste preview, alias-based column mapping, validation, duplicate detection, bulk import results and import batch tracking.
- Added the initial Foods import UI and documentation for spreadsheet workflows.

### Migration and compatibility

- Added Alembic migration `0006_food_library_imports`; existing foods, diary snapshots, profiles, plans, exercise, weight and hydration data are preserved.
- FoodHub remains a versioned external adapter and does not share or duplicate HealthHub's database.

### Deferred

- CSV/XLSX uploads, barcode/product databases, OCR extraction and full FoodHub recipe nutrition mapping remain roadmap items.
