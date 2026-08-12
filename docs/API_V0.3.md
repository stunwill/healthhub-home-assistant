# HealthHub v0.3 API additions

All routes remain under `/api/v1` and use the existing Home Assistant trust boundary. No user-authentication endpoints are introduced.

## Exercise

- `GET /profiles/{profile_id}/exercise`
  - optional `start` and `end` local dates
  - returns completed exercise entries
- `POST /profiles/{profile_id}/exercise`
  - requires activity name, duration minutes, calories burned and timezone-aware completion time
  - calories are user-supplied; HealthHub does not estimate them
- `DELETE /profiles/{profile_id}/exercise/{entry_id}`

## Weight

- `GET /profiles/{profile_id}/weights?days=90`
- `POST /profiles/{profile_id}/weights`
  - requires kilograms and a timezone-aware measurement time
- `DELETE /profiles/{profile_id}/weights/{entry_id}`

## Daily summary

`GET /profiles/{profile_id}/daily-summary?day=YYYY-MM-DD` now returns exercise-aware budget fields in addition to the existing food totals:

- `completed_exercise_calories`
- `credited_exercise_calories`
- `exercise_minutes`

The calculation remains:

`remaining = daily target - consumed food calories + credited exercise calories`

Credit is determined exclusively by the profile's configured `none`, `full` or `percentage` exercise-credit mode.

## Progress

`GET /profiles/{profile_id}/progress?days=90` returns:

- exercise minutes and calories within the requested period
- weekly exercise-minute target for context
- latest logged weight
- starting and goal weight when configured
- change from starting weight when available
- recent weight entries

HealthHub does not derive or prescribe weight or calorie targets from these values.
