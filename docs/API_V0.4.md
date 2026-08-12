# HealthHub API v0.4

HealthHub v0.4 keeps the versioned `/api/v1` surface and adds planning endpoints. Home Assistant remains the trust boundary, no authentication endpoints are added.

## Planned entries

- `GET /api/v1/profiles/{profile_id}/planned?start=YYYY-MM-DD&days=7`
- `POST /api/v1/profiles/{profile_id}/planned`
- `POST /api/v1/profiles/{profile_id}/planned/{entry_id}/consume`
- `POST /api/v1/profiles/{profile_id}/planned/{entry_id}/skip`
- `DELETE /api/v1/profiles/{profile_id}/planned/{entry_id}`

A planned entry snapshots the selected HealthHub food's serving and nutrition values. Consuming a plan creates a diary entry from that snapshot and links the planned entry to the created diary entry.

## Recurrence

- `GET /api/v1/profiles/{profile_id}/recurrence`
- `POST /api/v1/profiles/{profile_id}/recurrence`
- `POST /api/v1/profiles/{profile_id}/recurrence/{rule_id}/archive`

Supported frequencies are `daily`, `weekdays` and `weekly`. Rules materialise planned entries for up to eight weeks. Archiving a rule prevents it from being returned as active, it does not rewrite already-created planned entries.

## Weekly summary

- `GET /api/v1/profiles/{profile_id}/weekly-plan?start=YYYY-MM-DD`

The supplied date is normalised to the Monday of its week. The response contains seven daily rows plus aggregate planned and consumed calories.

## Boundaries

Planning endpoints accept HealthHub food IDs. FoodHub recipes are not treated as authoritative personal nutrition until the FoodHub integration contract can provide reliable per-serving nutrition.
