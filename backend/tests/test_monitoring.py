from datetime import datetime, timedelta, timezone

from app.monitoring import calculate_freshness


REFERENCE = datetime(
    2026, 10, 29,
    12, 0, 0,
    tzinfo=timezone.utc,
)


def test_fresh_reading():

    observed = REFERENCE - timedelta(minutes=5)

    status, age = calculate_freshness(
        observed,
        REFERENCE,
    )

    assert status == "fresh"
    assert age == 5.0


def test_fresh_at_boundary():

    observed = REFERENCE - timedelta(minutes=15)

    status, age = calculate_freshness(
        observed,
        REFERENCE,
    )

    assert status == "fresh"
    assert age == 15.0


def test_stale_after_boundary():

    observed = REFERENCE - timedelta(
        minutes=15,
        seconds=1,
    )

    status, age = calculate_freshness(
        observed,
        REFERENCE,
    )

    assert status == "stale"
    assert age > 15


def test_very_old_reading():

    observed = REFERENCE - timedelta(days=2)

    status, age = calculate_freshness(
        observed,
        REFERENCE,
    )

    assert status == "stale"


def test_missing_reading():

    status, age = calculate_freshness(
        None,
        REFERENCE,
    )

    assert status == "no_data"
    assert age is None