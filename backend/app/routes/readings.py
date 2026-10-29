from typing import Annotated, Literal
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Reading, Sensor
from app.schemas import ReadingCreate, ReadingResponse, MetricStatus, SensorStatusResponse
from app.monitoring import calculate_freshness, REPORTING_INTERVAL_MINUTES, STALE_AFTER_MINUTES


router = APIRouter(
    tags=["Readings"],
)


def require_sensor(
    sensor_id: int,
    db: Session,
) -> Sensor:
    """
    Check that a sensor exists and is active.
    """

    sensor = db.get(Sensor, sensor_id)

    if sensor is None or sensor.is_archived:
        raise HTTPException(
            status_code=404,
            detail="Sensor not found",
        )

    return sensor


@router.post(
    "/readings",
    response_model=ReadingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reading(
    reading_data: ReadingCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Validate and store a new sensor reading.
    """

    require_sensor(
        reading_data.sensor_id,
        db,
    )

    reading = Reading(
        sensor_id=reading_data.sensor_id,
        metric=reading_data.metric,
        value=reading_data.value,
        unit=reading_data.unit,
        observed_at=reading_data.observed_at,
    )

    db.add(reading)

    try:
        db.commit()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "A reading already exists for this "
                "sensor, metric and observation time"
            ),
        )

    db.refresh(reading)

    return reading


@router.get(
    "/sensors/{sensor_id}/readings",
    response_model=list[ReadingResponse],
)
def get_sensor_readings(
    sensor_id: int,
    db: Annotated[Session, Depends(get_db)],

    metric: Literal[
        "pm25",
        "temperature",
        "humidity",
    ] | None = None,

    start: datetime | None = None,
    end: datetime | None = None,

    limit: int = Query(
        default=100,
        ge=1,
        le=10000,
    ),
):
    """
    Retrieve readings for a sensor.

    Supports:
    - Optional metric filtering
    - Optional UTC date-range filtering
    - Result limits

    Date filtering uses:
        observed_at >= start
        observed_at < end

    Results are returned newest first.
    """

    require_sensor(sensor_id, db)

    for name, timestamp in (
        ("start", start),
        ("end", end),
    ):
        if timestamp is not None and timestamp.tzinfo is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{name} must include timezone information"
                ),
            )

    if start is not None:
        start = start.astimezone(timezone.utc)

    if end is not None:
        end = end.astimezone(timezone.utc)

    if (
        start is not None
        and end is not None
        and start >= end
    ):
        raise HTTPException(
            status_code=422,
            detail="start must be earlier than end",
        )

    statement = (
        select(Reading)
        .where(Reading.sensor_id == sensor_id)
    )

    if metric is not None:
        statement = statement.where(
            Reading.metric == metric
        )

    if start is not None:
        statement = statement.where(
            Reading.observed_at >= start
        )

    if end is not None:
        statement = statement.where(
            Reading.observed_at < end
        )

    statement = (
        statement
        .order_by(
            Reading.observed_at.desc(),
            Reading.id.desc(),
        )
        .limit(limit)
    )

    return db.scalars(statement).all()


@router.get(
    "/sensors/{sensor_id}/latest",
    response_model=list[ReadingResponse],
)
def get_latest_readings(
    sensor_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Retrieve the latest reading for each metric.
    """

    require_sensor(sensor_id, db)

    metrics = [
        "pm25",
        "temperature",
        "humidity",
    ]

    latest_readings = []

    for metric in metrics:

        statement = (
            select(Reading)
            .where(
                Reading.sensor_id == sensor_id,
                Reading.metric == metric,
            )
            .order_by(
                Reading.observed_at.desc(),
                Reading.id.desc(),
            )
            .limit(1)
        )

        reading = db.scalar(statement)

        if reading is not None:
            latest_readings.append(reading)

    return latest_readings

@router.get(
    "/sensors/{sensor_id}/status",
    response_model=SensorStatusResponse,
)
def get_sensor_status(
    sensor_id: int,
    db: Annotated[Session, Depends(get_db)],
    as_of: datetime | None = None,
):
    """
    Retrieve latest measurements and freshness status.

    as_of can be used to inspect historical status.
    Defaults to the current UTC time.
    """

    sensor = require_sensor(sensor_id, db)

    if as_of is not None and as_of.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail="as_of must include timezone information",
        )

    reference_time = (
        as_of.astimezone(timezone.utc)
        if as_of is not None
        else datetime.now(timezone.utc)
    )

    metrics = [
        "pm25",
        "temperature",
        "humidity",
    ]

    metric_statuses = []

    for metric in metrics:

        statement = (
            select(Reading)
            .where(
                Reading.sensor_id == sensor_id,
                Reading.metric == metric,
                Reading.observed_at <= reference_time,
            )
            .order_by(
                Reading.observed_at.desc(),
                Reading.id.desc(),
            )
            .limit(1)
        )

        reading = db.scalar(statement)

        if reading is None:

            metric_statuses.append(
                MetricStatus(
                    metric=metric,
                    status="no_data",
                    latest_reading=None,
                    age_minutes=None,
                )
            )

            continue

        freshness, age = calculate_freshness(
            reading.observed_at,
            reference_time,
        )

        metric_statuses.append(
            MetricStatus(
                metric=metric,
                status=freshness,
                latest_reading=reading,
                age_minutes=age,
            )
        )

    return SensorStatusResponse(
        sensor_id=sensor.id,
        sensor_name=sensor.name,
        source_type=sensor.source_type,
        reporting_interval_minutes=(
            REPORTING_INTERVAL_MINUTES
        ),
        stale_after_minutes=STALE_AFTER_MINUTES,
        checked_at=reference_time,
        metrics=metric_statuses,
    )