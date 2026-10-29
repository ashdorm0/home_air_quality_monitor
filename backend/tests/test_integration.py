import os

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import Location, Reading, Sensor

@pytest.fixture(autouse=True)
def verify_test_database():
    """
    Refuse to execute integration tests unless
    the dedicated test database is configured.
    """

    database_name = os.getenv("DB_NAME")

    if database_name != "air_quality_test":
        pytest.fail(
            "Integration tests require "
            "DB_NAME=air_quality_test"
        )
        
        
@pytest.fixture
def test_sensors():

    with SessionLocal() as db:

        indoor_location = Location(
            name="Integration Test Living Room",
            placement="indoor",
        )

        outdoor_location = Location(
            name="Integration Test Garden",
            placement="outdoor",
        )

        db.add_all([
            indoor_location,
            outdoor_location,
        ])

        db.flush()

        indoor_sensor = Sensor(
            name="Integration Test Indoor Sensor",
            location_id=indoor_location.id,
            source_type="simulated",
        )

        outdoor_sensor = Sensor(
            name="Integration Test Outdoor Sensor",
            location_id=outdoor_location.id,
            source_type="simulated",
        )

        db.add_all([
            indoor_sensor,
            outdoor_sensor,
        ])

        db.commit()

        indoor_id = indoor_sensor.id
        outdoor_id = outdoor_sensor.id

        indoor_location_id = indoor_location.id
        outdoor_location_id = outdoor_location.id

    yield indoor_id, outdoor_id

    # Remove only records created by this fixture.
    with SessionLocal() as db:

        db.query(Reading).filter(
            Reading.sensor_id.in_([
                indoor_id,
                outdoor_id,
            ])
        ).delete(synchronize_session=False)

        db.query(Sensor).filter(
            Sensor.id.in_([
                indoor_id,
                outdoor_id,
            ])
        ).delete(synchronize_session=False)

        db.query(Location).filter(
            Location.id.in_([
                indoor_location_id,
                outdoor_location_id,
            ])
        ).delete(synchronize_session=False)

        db.commit()
        
def test_simulator_to_database(test_sensors):

    indoor_id, outdoor_id = test_sensors

    # Generate one hour of measurements.
    readings = generate_readings(
        indoor_sensor_id=indoor_id,
        outdoor_sensor_id=outdoor_id,
        start=START,
        steps=12,
        seed=42,
    )

    assert len(readings) == 72

    # Upload every reading through FastAPI.
    for reading in readings:

        response = client.post(
            "/readings",
            json=reading,
        )

        assert response.status_code == 201, (
            response.text
        )

    # Verify the records really exist in PostgreSQL.
    with SessionLocal() as db:

        count = db.scalar(
            select(func.count(Reading.id))
            .where(
                Reading.sensor_id.in_([
                    indoor_id,
                    outdoor_id,
                ])
            )
        )

        assert count == 72

    # Retrieve readings through the API.
    response = client.get(
        f"/sensors/{indoor_id}/readings",
        params={
            "metric": "pm25",
            "start": START.isoformat(),
            "end": (
                START + timedelta(hours=1)
            ).isoformat(),
            "limit": 100,
        },
    )

    assert response.status_code == 200

    stored = response.json()

    assert len(stored) == 12

    # Compare every returned PM2.5 observation.
    expected = {
        reading["observed_at"]: reading["value"]
        for reading in readings
        if (
            reading["sensor_id"] == indoor_id
            and reading["metric"] == "pm25"
        )
    }

    actual = {
        datetime.fromisoformat(
            reading["observed_at"].replace(
                "Z", "+00:00"
            )
        ).isoformat(): reading["value"]
        for reading in stored
    }

    normalised_expected = {
        datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        ).isoformat(): value
        for timestamp, value in expected.items()
    }

    assert actual == normalised_expected

    # Verify returned units and timestamps.
    for reading in stored:

        assert reading["unit"] == "µg/m³"

        assert reading["received_at"] is not None

        assert reading["observed_at"] is not None
        
def test_duplicate_replay(test_sensors):

    indoor_id, outdoor_id = test_sensors

    readings = generate_readings(
        indoor_sensor_id=indoor_id,
        outdoor_sensor_id=outdoor_id,
        start=START,
        steps=12,
        seed=42,
    )

    # First replay: all readings created.
    for reading in readings:

        response = client.post(
            "/readings",
            json=reading,
        )

        assert response.status_code == 201

    # Second replay: all readings rejected as duplicates.
    for reading in readings:

        response = client.post(
            "/readings",
            json=reading,
        )

        assert response.status_code == 409

    # Verify that PostgreSQL still contains 72 records.
    with SessionLocal() as db:

        count = db.scalar(
            select(func.count(Reading.id))
            .where(
                Reading.sensor_id.in_([
                    indoor_id,
                    outdoor_id,
                ])
            )
        )

        assert count == 72
        
def test_historical_date_filtering(test_sensors):

    indoor_id, outdoor_id = test_sensors

    readings = generate_readings(
        indoor_sensor_id=indoor_id,
        outdoor_sensor_id=outdoor_id,
        start=START,
        steps=12,
        seed=42,
    )

    for reading in readings:

        response = client.post(
            "/readings",
            json=reading,
        )

        assert response.status_code == 201

    # Request only the first 30 minutes.
    response = client.get(
        f"/sensors/{indoor_id}/readings",
        params={
            "metric": "pm25",
            "start": START.isoformat(),
            "end": (
                START + timedelta(minutes=30)
            ).isoformat(),
        },
    )

    assert response.status_code == 200

    result = response.json()

    # 00:00, 00:05, 00:10, 00:15, 00:20, 00:25
    assert len(result) == 6

    # Reversed ranges must be rejected.
    invalid_response = client.get(
        f"/sensors/{indoor_id}/readings",
        params={
            "start": (
                START + timedelta(hours=1)
            ).isoformat(),
            "end": START.isoformat(),
        },
    )

    assert invalid_response.status_code == 422
    
def test_sensor_freshness_status(test_sensors):

    indoor_id, outdoor_id = test_sensors

    readings = generate_readings(
        indoor_sensor_id=indoor_id,
        outdoor_sensor_id=outdoor_id,
        start=START,
        steps=12,
        seed=42,
    )

    for reading in readings:

        response = client.post(
            "/readings",
            json=reading,
        )

        assert response.status_code == 201

    # Last observation occurs at 00:55.
    # Check the status at 01:00.
    fresh_reference = START + timedelta(hours=1)

    response = client.get(
        f"/sensors/{indoor_id}/status",
        params={
            "as_of": fresh_reference.isoformat(),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["sensor_id"] == indoor_id
    assert data["source_type"] == "simulated"

    assert all(
        metric["status"] == "fresh"
        for metric in data["metrics"]
    )

    # Check the same readings 30 minutes later.
    stale_reference = START + timedelta(
        hours=1,
        minutes=30,
    )

    response = client.get(
        f"/sensors/{indoor_id}/status",
        params={
            "as_of": stale_reference.isoformat(),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert all(
        metric["status"] == "stale"
        for metric in data["metrics"]
    )       
    
def test_missing_data_gap(test_sensors):

    indoor_id, outdoor_id = test_sensors

    readings = generate_readings(
        indoor_sensor_id=indoor_id,
        outdoor_sensor_id=outdoor_id,
        start=START,
        steps=288,
        seed=42,
    )

    assert len(readings) == 1692

    # Upload the full historical dataset.
    for reading in readings:

        response = client.post(
            "/readings",
            json=reading,
        )

        assert response.status_code == 201

    outage_start = START + timedelta(hours=18)
    outage_end = START + timedelta(hours=19)

    # Indoor sensor: no readings during outage.
    indoor_response = client.get(
        f"/sensors/{indoor_id}/readings",
        params={
            "start": outage_start.isoformat(),
            "end": outage_end.isoformat(),
        },
    )

    assert indoor_response.status_code == 200
    assert indoor_response.json() == []

    # Outdoor sensor: still reports normally.
    outdoor_response = client.get(
        f"/sensors/{outdoor_id}/readings",
        params={
            "start": outage_start.isoformat(),
            "end": outage_end.isoformat(),
        },
    )

    assert outdoor_response.status_code == 200
    assert len(outdoor_response.json()) == 36

    # Check that indoor readings become stale.
    status_response = client.get(
        f"/sensors/{indoor_id}/status",
        params={
            "as_of": (
                outage_start + timedelta(minutes=20)
            ).isoformat(),
        },
    )

    assert status_response.status_code == 200

    statuses = status_response.json()["metrics"]

    assert all(
        metric["status"] == "stale"
        for metric in statuses
    )
    
# Import the simulator package from the project root
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(PROJECT_ROOT))

from simulator.simulator import generate_readings


client = TestClient(app)


START = datetime(
    2026, 10, 27,
    0, 0, 0,
    tzinfo=timezone.utc,
)