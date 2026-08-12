from __future__ import annotations

from datetime import date

from sqlalchemy import event

from .models import RecurrenceRule


@event.listens_for(RecurrenceRule, "before_insert")
@event.listens_for(RecurrenceRule, "before_update")
def normalise_recurrence_dates(_mapper, _connection, target: RecurrenceRule) -> None:  # type: ignore[no-untyped-def]
    if isinstance(target.start_date, str):
        target.start_date = date.fromisoformat(target.start_date)
    if isinstance(target.end_date, str):
        target.end_date = date.fromisoformat(target.end_date)
