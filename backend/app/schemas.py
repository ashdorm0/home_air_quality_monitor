from datetime import datetime, timezone
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class LocationResponse(BaseModel):
    id: int
    name: str
    placement: str
    is_archived: bool

    model_config = ConfigDict(from_attributes=True)


class SensorResponse(BaseModel):
    id: int
    name: str
    location_id: int
    source_type: str
    is_archived: bool

    model_config = ConfigDict(from_attributes=True)


class ReadingCreate(BaseModel):
    sensor_id: int = Field(gt=0)

    metric: Literal[
        "pm25",
        "temperature",
        "humidity",
    ]

    value: float

    unit: str

    observed_at: datetime

    @field_validator("value")
    @classmethod
    def validate_finite_value(cls, value):
        import math

        if not math.isfinite(value):
            raise ValueError(
                "Reading value must be finite"
            )

        return value

    @field_validator("observed_at")
    @classmethod
    def validate_timestamp(cls, value):

        if value.tzinfo is None:
            raise ValueError(
                "Timestamp must include timezone information"
            )

        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_measurement(self):

        allowed_units = {
            "pm25": "µg/m³",
            "temperature": "°C",
            "humidity": "%",
        }

        expected_unit = allowed_units[self.metric]

        if self.unit != expected_unit:
            raise ValueError(
                f"Invalid unit for {self.metric}. "
                f"Expected {expected_unit}"
            )

        if self.metric == "pm25":
            if not 0 <= self.value <= 1000:
                raise ValueError(
                    "PM2.5 must be between 0 and 1000"
                )

        elif self.metric == "temperature":
            if not -50 <= self.value <= 80:
                raise ValueError(
                    "Temperature must be between -50 and 80"
                )

        elif self.metric == "humidity":
            if not 0 <= self.value <= 100:
                raise ValueError(
                    "Humidity must be between 0 and 100"
                )

        return self


class ReadingResponse(BaseModel):
    id: int
    sensor_id: int
    metric: str
    value: float
    unit: str
    observed_at: datetime
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)
    
class MetricStatus(BaseModel):
    metric: str

    status: Literal[
        "fresh",
        "stale",
        "no_data",
    ]

    latest_reading: ReadingResponse | None

    age_minutes: float | None


class SensorStatusResponse(BaseModel):
    sensor_id: int
    sensor_name: str
    source_type: str

    reporting_interval_minutes: int
    stale_after_minutes: int

    checked_at: datetime

    metrics: list[MetricStatus]