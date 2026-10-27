from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Sensor
from app.schemas import SensorResponse


router = APIRouter(
    prefix="/sensors",
    tags=["Sensors"],
)


@router.get(
    "",
    response_model=list[SensorResponse],
)
def get_sensors(
    db: Annotated[Session, Depends(get_db)],
):
    """
    Retrieve all active sensors.
    """

    statement = (
        select(Sensor)
        .where(Sensor.is_archived.is_(False))
        .order_by(Sensor.id)
    )

    sensors = db.scalars(statement).all()

    return sensors


@router.get(
    "/{sensor_id}",
    response_model=SensorResponse,
)
def get_sensor(
    sensor_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Retrieve a sensor by its ID.
    """

    sensor = db.get(Sensor, sensor_id)

    if sensor is None or sensor.is_archived:
        raise HTTPException(
            status_code=404,
            detail="Sensor not found",
        )

    return sensor