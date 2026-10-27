from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    placement: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    sensors: Mapped[list["Sensor"]] = relationship(
        back_populates="location",
    )

    __table_args__ = (
        CheckConstraint(
            "placement IN ('indoor', 'outdoor')",
            name="ck_location_placement",
        ),
    )


class Sensor(Base):
    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id"),
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="simulated",
    )

    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    location: Mapped["Location"] = relationship(
        back_populates="sensors",
    )

    readings: Mapped[list["Reading"]] = relationship(
        back_populates="sensor",
    )

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('simulated', 'physical')",
            name="ck_sensor_source_type",
        ),
    )


class Reading(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    sensor_id: Mapped[int] = mapped_column(
        ForeignKey("sensors.id"),
        nullable=False,
    )

    metric: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    sensor: Mapped["Sensor"] = relationship(
        back_populates="readings",
    )

    __table_args__ = (
        UniqueConstraint(
            "sensor_id",
            "metric",
            "observed_at",
            name="uq_sensor_metric_observed_at",
        ),
        Index(
            "ix_readings_sensor_metric_time",
            "sensor_id",
            "metric",
            "observed_at",
        ),
    )