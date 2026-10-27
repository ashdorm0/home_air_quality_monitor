from datetime import datetime, timezone
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Location, Reading, Sensor


client = TestClient(app)


@pytest.fixture
def test_sensor():
    """
    Create a dedicated sensor for each test.

    Remove its readings, the sensor, and its
    location after the test completes.
    """

    unique_name = f"Test Location {uuid4().hex[:8]}"

    with SessionLocal() as db:

        location = Location(
            name=unique_name,
            placement="indoor",
        )

        db.add(location)
        db.flush()

        sensor = Sensor(
            name=f"{unique_name} Sensor",
            location_id=location.id,
            source_type="simulated",
        )

        db.add(sensor)
        db.commit()

        sensor_id = sensor.id
        location_id = location.id

    yield sensor_id

    with SessionLocal() as db:

        readings = db.query(Reading).filter(
            Reading.sensor_id == sensor_id
        ).all()

        for reading in readings:
            db.delete(reading)

        sensor = db.get(Sensor, sensor_id)

        if sensor is not None:
            db.delete(sensor)

        location = db.get(Location, location_id)

        if location is not None:
            db.delete(location)

        db.commit()


def make_reading(sensor_id, metric="pm25"):
    """
    Generate a valid test reading.
    """

    units = {
        "pm25": "µg/m³",
        "temperature": "°C",
        "humidity": "%",
    }

    values = {
        "pm25": 15.5,
        "temperature": 21.0,
        "humidity": 50.0,
    }

    return {
        "sensor_id": sensor_id,
        "metric": metric,
        "value": values[metric],
        "unit": units[metric],
        "observed_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def test_locations_endpoint():

    response = client.get("/locations")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_sensors_endpoint():

    response = client.get("/sensors")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_valid_reading(test_sensor):

    payload = make_reading(test_sensor)

    response = client.post(
        "/readings",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["sensor_id"] == test_sensor
    assert data["metric"] == "pm25"
    assert data["value"] == 15.5
    assert data["unit"] == "µg/m³"
    assert "received_at" in data


def test_reject_invalid_unit(test_sensor):

    payload = make_reading(test_sensor)

    payload["unit"] = "%"

    response = client.post(
        "/readings",
        json=payload,
    )

    assert response.status_code == 422


def test_reject_negative_pm25(test_sensor):

    payload = make_reading(test_sensor)

    payload["value"] = -10

    response = client.post(
        "/readings",
        json=payload,
    )

    assert response.status_code == 422


def test_reject_unknown_sensor():

    payload = make_reading(999999999)

    response = client.post(
        "/readings",
        json=payload,
    )

    assert response.status_code == 404


def test_prevent_duplicate_reading(test_sensor):

    payload = make_reading(test_sensor)

    first_response = client.post(
        "/readings",
        json=payload,
    )

    second_response = client.post(
        "/readings",
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_get_historical_readings(test_sensor):

    payload = make_reading(test_sensor)

    create_response = client.post(
        "/readings",
        json=payload,
    )

    assert create_response.status_code == 201

    response = client.get(
        f"/sensors/{test_sensor}/readings",
        params={"metric": "pm25"},
    )

    assert response.status_code == 200

    readings = response.json()

    assert len(readings) == 1
    assert readings[0]["metric"] == "pm25"


def test_get_latest_readings(test_sensor):

    metrics = [
        "pm25",
        "temperature",
        "humidity",
    ]

    for metric in metrics:

        payload = make_reading(
            test_sensor,
            metric,
        )

        response = client.post(
            "/readings",
            json=payload,
        )

        assert response.status_code == 201

    response = client.get(
        f"/sensors/{test_sensor}/latest"
    )

    assert response.status_code == 200

    readings = response.json()

    assert len(readings) == 3

    returned_metrics = {
        reading["metric"]
        for reading in readings
    }

    assert returned_metrics == set(metrics)