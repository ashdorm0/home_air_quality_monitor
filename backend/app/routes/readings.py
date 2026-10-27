from typing import Annotated, Literal

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
from app.schemas import ReadingCreate, ReadingResponse


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
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
):
    """
    Retrieve historical readings for a sensor.
    """

    require_sensor(sensor_id, db)

    statement = (
        select(Reading)
        .where(Reading.sensor_id == sensor_id)
    )

    if metric is not None:
        statement = statement.where(
            Reading.metric == metric
        )

    statement = (
        statement
        .order_by(Reading.observed_at.desc())
        .limit(limit)
    )

    readings = db.scalars(statement).all()

    return readings


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