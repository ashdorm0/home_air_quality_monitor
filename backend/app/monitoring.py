from datetime import datetime, timezone


# Sensor reporting configuration
REPORTING_INTERVAL_MINUTES = 5
MISSED_INTERVAL_LIMIT = 3

STALE_AFTER_MINUTES = (
    REPORTING_INTERVAL_MINUTES * MISSED_INTERVAL_LIMIT
)


def calculate_freshness(
    observed_at: datetime | None,
    reference_time: datetime,
) -> tuple[str, float | None]:
    """
    Calculate the freshness of a sensor measurement.

    A reading is:
    - fresh: 15 minutes old or less
    - stale: more than 15 minutes old
    - no_data: no observation exists

    Returns:
        (status, age_minutes)
    """

    if reference_time.tzinfo is None:
        raise ValueError(
            "Reference time must include timezone information"
        )

    if observed_at is None:
        return "no_data", None

    if observed_at.tzinfo is None:
        raise ValueError(
            "Observation time must include timezone information"
        )

    observed_at = observed_at.astimezone(timezone.utc)
    reference_time = reference_time.astimezone(timezone.utc)

    age_seconds = (
        reference_time - observed_at
    ).total_seconds()

    if age_seconds < 0:
        raise ValueError(
            "Observation timestamp is after reference time"
        )

    age_minutes = age_seconds / 60

    if age_minutes <= STALE_AFTER_MINUTES:
        status = "fresh"
    else:
        status = "stale"

    return status, round(age_minutes, 2)