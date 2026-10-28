import argparse
import json
import math
import random
import sys

from datetime import datetime, timedelta, timezone

import httpx


METRIC_UNITS = {
    "pm25": "µg/m³",
    "temperature": "°C",
    "humidity": "%",
}

INTERVAL_MINUTES = 5
DEFAULT_STEPS = 288
DEFAULT_SEED = 42

DEFAULT_START = "2026-10-27T00:00:00Z"

DEFAULT_API_URL = "http://127.0.0.1:8000"

def generate_values(
    rng: random.Random,
    sensor_type: str,
    step: int,
    steps_per_day: int = 288,
) -> dict[str, float]:
    """
    Generate PM2.5, temperature and humidity values.

    Includes:
    - Baseline variation
    - Indoor PM2.5 spike
    - Elevated outdoor PM2.5
    """

    phase = 2 * math.pi * (step % steps_per_day) / steps_per_day

    if sensor_type == "indoor":

        pm25 = 8.0 + rng.uniform(-2.0, 2.0)

        temperature = (
            21.0
            + 1.5 * math.sin(phase)
            + rng.uniform(-0.5, 0.5)
        )

        humidity = (
            48.0
            + 5.0 * math.sin(phase)
            + rng.uniform(-3.0, 3.0)
        )

        # Indoor pollution spike:
        # 06:00–06:55 UTC, on the first simulated day
        if 72 <= step < 84:
            pm25 += rng.uniform(25.0, 45.0)

    elif sensor_type == "outdoor":

        pm25 = 11.0 + rng.uniform(-3.0, 3.0)

        temperature = (
            14.0
            + 4.0 * math.sin(phase)
            + rng.uniform(-1.0, 1.0)
        )

        humidity = (
            65.0
            + 8.0 * math.sin(phase)
            + rng.uniform(-4.0, 4.0)
        )

        # Outdoor pollution elevation:
        # 12:00–13:55 UTC, on the first simulated day
        if 144 <= step < 168:
            pm25 += rng.uniform(15.0, 30.0)

    else:
        raise ValueError(
            f"Unsupported sensor type: {sensor_type}"
        )

    return {
        "pm25": round(max(0.0, pm25), 2),
        "temperature": round(temperature, 2),
        "humidity": round(
            min(100.0, max(0.0, humidity)),
            2,
        ),
    }
    
def generate_readings(
    indoor_sensor_id: int,
    outdoor_sensor_id: int,
    start: datetime,
    steps: int = DEFAULT_STEPS,
    seed: int = DEFAULT_SEED,
) -> list[dict]:
    """
    Generate reproducible indoor and outdoor readings.

    Each step represents five minutes.

    On the first simulated day, the indoor sensor
    has an outage from 18:00 to 18:55 UTC.
    """

    if indoor_sensor_id <= 0 or outdoor_sensor_id <= 0:
        raise ValueError("Sensor IDs must be positive")

    if indoor_sensor_id == outdoor_sensor_id:
        raise ValueError(
            "Indoor and outdoor sensors must have different IDs"
        )

    if steps <= 0:
        raise ValueError("Steps must be positive")

    if start.tzinfo is None:
        raise ValueError(
            "Simulation start time must include timezone information"
        )

    start = start.astimezone(timezone.utc)

    rng = random.Random(seed)

    readings = []

    sensors = [
        (indoor_sensor_id, "indoor"),
        (outdoor_sensor_id, "outdoor"),
    ]

    for step in range(steps):

        timestamp = start + timedelta(
            minutes=step * INTERVAL_MINUTES
        )

        observed_at = (
            timestamp
            .isoformat()
            .replace("+00:00", "Z")
        )

        for sensor_id, sensor_type in sensors:

            # Simulated indoor outage:
            # 18:00–18:55 on the first simulated day
            if (
                sensor_type == "indoor"
                and 216 <= step < 228
            ):
                continue

            values = generate_values(
                rng=rng,
                sensor_type=sensor_type,
                step=step,
            )

            for metric, value in values.items():

                reading = {
                    "sensor_id": sensor_id,
                    "metric": metric,
                    "value": value,
                    "unit": METRIC_UNITS[metric],
                    "observed_at": observed_at,
                }

                readings.append(reading)

    return readings

def replay_readings(
    readings: list[dict],
    api_base_url: str = DEFAULT_API_URL,
) -> tuple[int, int]:
    """
    Upload historical readings to FastAPI.

    Returns:
        (created_count, duplicate_count)

    Stops if an unexpected API error occurs.
    """

    created_count = 0
    duplicate_count = 0

    url = f"{api_base_url.rstrip('/')}/readings"

    with httpx.Client(timeout=10.0) as client:

        for index, reading in enumerate(readings, start=1):

            try:
                response = client.post(
                    url,
                    json=reading,
                )

            except httpx.RequestError as exc:
                raise RuntimeError(
                    f"Could not connect to FastAPI: {exc}"
                ) from exc

            if response.status_code == 201:
                created_count += 1

            elif response.status_code == 409:
                duplicate_count += 1

            else:
                raise RuntimeError(
                    "Reading upload failed.\n"
                    f"Status: {response.status_code}\n"
                    f"Reading: {reading}\n"
                    f"Response: {response.text}"
                )

            if index % 100 == 0:
                print(
                    f"Processed {index}/{len(readings)} readings"
                )

    return created_count, duplicate_count

def parse_start_time(value: str) -> datetime:
    """
    Parse an ISO 8601 datetime with timezone information.
    """

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Start time must be an ISO 8601 datetime"
        ) from exc

    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError(
            "Start time must include a timezone"
        )

    return parsed.astimezone(timezone.utc)


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Home Air Quality Monitor sensor simulator"
        )
    )

    parser.add_argument(
        "--mode",
        choices=["preview", "replay"],
        default="preview",
        help="Preview readings or upload them to FastAPI",
    )

    parser.add_argument(
        "--indoor-sensor-id",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--outdoor-sensor-id",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
    )

    parser.add_argument(
        "--steps",
        type=int,
        default=DEFAULT_STEPS,
        help="Number of five-minute intervals",
    )

    parser.add_argument(
        "--start",
        type=parse_start_time,
        default=parse_start_time(DEFAULT_START),
    )

    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
    )

    parser.add_argument(
        "--preview-count",
        type=int,
        default=9,
    )

    args = parser.parse_args()

    if args.preview_count < 1:
        parser.error("--preview-count must be positive")

    try:
        readings = generate_readings(
            indoor_sensor_id=args.indoor_sensor_id,
            outdoor_sensor_id=args.outdoor_sensor_id,
            start=args.start,
            steps=args.steps,
            seed=args.seed,
        )

        print("\nHome Air Quality Monitor Simulator")
        print("----------------------------------")
        print(f"Mode: {args.mode}")
        print(f"Seed: {args.seed}")
        print(f"Start: {args.start.isoformat()}")
        print(f"Intervals: {args.steps}")
        print(f"Readings generated: {len(readings)}")

        if args.mode == "preview":

            print("\nSample readings:\n")

            for reading in readings[:args.preview_count]:
                print(
                    json.dumps(
                        reading,
                        indent=2,
                        ensure_ascii=False,
                    )
                )

            print("\nPreview completed.")
            print("No readings were uploaded.")

        elif args.mode == "replay":

            print("\nUploading readings to FastAPI...\n")

            created, duplicates = replay_readings(
                readings=readings,
                api_base_url=args.api_url,
            )

            print("\nReplay completed.")
            print(f"Created: {created}")
            print(f"Duplicates: {duplicates}")
            print(f"Total processed: {created + duplicates}")

    except (ValueError, RuntimeError) as exc:

        print(
            f"\nSimulator error: {exc}",
            file=sys.stderr,
        )

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())