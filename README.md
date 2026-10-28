# Home Air Quality Monitor

Fourth-year capstone project — SETU Carlow  
Project specification dated **9 October 2026**

## Overview

The **Home Air Quality Monitor** is a planned web application for homeowners to monitor indoor and outdoor air quality, compare measurements across locations, and understand PM2.5 readings in the context of published guidance. The initial prototype uses **synthetic data**, so development does not depend on physical sensor hardware.

The intended full system supports multiple indoor locations and one outdoor location per household. Initial metrics are:

| Metric | Unit | Use |
| --- | --- | --- |
| PM2.5 | µg/m³ | Air quality measurements and eventual guidance comparisons |
| Temperature | °C | Contextual measurement |
| Relative humidity | % | Contextual measurement |

Temperature and humidity will **not** contribute to an AQI calculation.

> The project is not yet feature-complete or ready for public deployment. Current ingestion endpoints are unauthenticated and intended for **local development only**.

## Planned architecture

```text
Python simulator (synthetic data)
             |
             | JSON / HTTP POST
             v
       FastAPI REST API
             |
      Pydantic validation
             |
       SQLAlchemy ORM
             |
       PostgreSQL database
             |
       REST read endpoints
             |
       React dashboard (future)
```

Core technology choices follow the project specification: **Python**, **FastAPI**, **PostgreSQL**, and a future **React** dashboard. Docker Compose is used for the local development database. Alembic manages schema migrations; HTTPX is used by the simulator.

## Prerequisites

- Python 3.12 or another compatible supported Python version
- Docker Engine/Desktop with Docker Compose
- Git (recommended)
- A terminal; VS Code is optional

## Local setup

The commands below assume the repository root is `~/capstone` on Linux. Run them from the **repository root** unless otherwise indicated.

### 1. Create and activate a Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

The Day 1–3 dependencies include FastAPI (with Uvicorn), SQLAlchemy, Psycopg, python-dotenv, pytest, Alembic and HTTPX.

### 2. Configure local environment variables

```bash
cp .env.example .env
```

Edit `.env` for your local configuration:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=air_quality_db
DB_USER=air_quality_user
DB_PASSWORD=choose_a_private_local_password
```

Use the same database name/user/password as the Docker Compose service. **Never commit `.env`**. Only `.env.example` belongs in source control.

### 3. Start PostgreSQL

```bash
docker compose up -d
docker compose ps
```

Wait until the database is healthy. The Docker database uses persistent storage, so routine stop/start operations should retain your data.

### 4. Apply database migrations

```bash
cd backend
python -m alembic upgrade head
```

This creates the database schema defined by the SQLAlchemy models, if the migration has been generated as described.

### 5. Seed development locations and sensors

From `backend/`:

```bash
python -m app.seed
```

The seed script creates example locations and simulated sensors for **Living Room (indoor)** and **Garden (outdoor)**. IDs are assigned by PostgreSQL and **must not be assumed to be `1` and `2`**.

### 6. Start the API

From `backend/`:

```bash
python -m uvicorn app.main:app --reload
```

Alternatively, from the repository root:

```bash
python -m uvicorn app.main:app --app-dir backend --reload
```

Useful local URLs:

- Health check: <http://127.0.0.1:8000/health>
- API documentation (Swagger UI): <http://127.0.0.1:8000/docs>
- Sensors: <http://127.0.0.1:8000/sensors>

Expected healthy database response:

```json
{
  "status": "healthy",
  "database": "connected"
}
```

If `/sensors` returns `[]`, ensure the seed script ran successfully. If it returns `404`, check that `sensors.router` is registered in `backend/app/main.py`.

## Database model

The initial schema contains:

- **Location:** name, indoor/outdoor placement, archived status.
- **Sensor:** associated location, name, source type (`simulated` or `physical`), archived status.
- **Reading:** sensor ID, metric, value, unit, observation time and receipt time.

Relations: **Location → Sensors → Readings** (one-to-many at each step).

The design enforces uniqueness for the combination of **sensor ID + metric + observation timestamp**. The incoming timestamp must be timezone-aware and is normalised to UTC. Invalid metric/unit combinations and out-of-range values are rejected. Range limits currently used in the prototype are engineering validation choices, **not** WHO/EPA health categories.

## API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | API information |
| `GET` | `/health` | Database connectivity |
| `GET` | `/locations` | List active locations |
| `GET` | `/sensors` | List active sensors |
| `GET` | `/sensors/{sensor_id}` | Get a sensor |
| `POST` | `/readings` | Validate and store a reading |
| `GET` | `/sensors/{sensor_id}/readings` | Historical readings; optional `metric` and `limit` |
| `GET` | `/sensors/{sensor_id}/latest` | Latest stored reading for each available metric |

Confirm their availability in `/docs` against the running application.

### Example: submit a PM2.5 reading

First, query `GET /sensors` to find a valid, active sensor ID. Replace `1` below with that ID:

```bash
curl -X POST http://127.0.0.1:8000/readings \
  -H 'Content-Type: application/json' \
  -d '{
    "sensor_id": 1,
    "metric": "pm25",
    "value": 23.4,
    "unit": "µg/m³",
    "observed_at": "2026-10-27T10:38:44Z"
  }'
```

Expected statuses

| Status | Meaning |
| --- | --- |
| `201 Created` | Reading stored |
| `422 Unprocessable Entity` | Invalid JSON field, metric, unit, range or timestamp |
| `404 Not Found` | Sensor ID not found or sensor archived |
| `409 Conflict` | Reading already exists for that sensor/metric/timestamp |

Swagger's sample `sensor_id` is just a placeholder; **posting a reading does not create a sensor**.

## Sensor simulator (Day 3)

The simulator generates **synthetic**, reproducible readings for one indoor and one outdoor sensor. The default dataset begins at `2026-10-27T00:00:00Z`, uses seed `42`, and covers **288 five-minute observation intervals (24 hours)**.

### Simulated events

| Scenario | Time (UTC, default day) | Behaviour |
| --- | --- | --- |
| Baseline | Most intervals | Variation around demonstration values |
| Indoor PM2.5 spike | 06:00–06:55 | Indoor PM2.5 increases |
| Outdoor PM2.5 elevation | 12:00–13:55 | Outdoor PM2.5 increases |
| Indoor sensor outage | 18:00–18:55 | Indoor sensor submits no readings; outdoor sensor continues |

During the outage, missing observations are **omitted**, not stored as zero values.

Expected counts for the default 24-hour dataset:

| Source | Readings |
| --- | ---: |
| Indoor sensor | 828 (276 intervals × 3 metrics) |
| Outdoor sensor | 864 (288 intervals × 3 metrics) |
| **Total** | **1,692** |

### Preview: no database writes

From the **repository root**, with `.venv` activated:

```bash
python -m simulator.simulator \
  --mode preview \
  --indoor-sensor-id 1 \
  --outdoor-sensor-id 2 \
  --seed 42
```

Replace both IDs with those returned by `GET /sensors` if needed. Preview mode generates the data locally **without checking whether the IDs exist in PostgreSQL**.

**Confirmed output from this project's Day 3 run:**

```text
Home Air Quality Monitor Simulator
----------------------------------
Mode: preview
Seed: 42
Start: 2026-10-27T00:00:00+00:00
Intervals: 288
Readings generated: 1692
...
Preview completed.
No readings were uploaded.
```

### Check deterministic output

```bash
python -m simulator.simulator --mode preview \
  --indoor-sensor-id 1 --outdoor-sensor-id 2 --seed 42 > preview1.txt

python -m simulator.simulator --mode preview \
  --indoor-sensor-id 1 --outdoor-sensor-id 2 --seed 42 > preview2.txt

diff -s preview1.txt preview2.txt
```

`>` writes terminal output to a file instead of printing it. Identical files indicate repeatable preview output for the same parameters. The **result of this repeatability comparison has not yet been reported**.

### Replay readings to FastAPI

Ensure PostgreSQL and FastAPI are running, then, from the **repository root**:

```bash
# Small end-to-end test: 12 intervals × 2 sensors × 3 metrics = 72 readings
python -m simulator.simulator \
  --mode replay \
  --indoor-sensor-id 1 \
  --outdoor-sensor-id 2 \
  --steps 12
```

Once the small replay succeeds:

```bash
# Complete 24-hour dataset: 1,692 generated readings
python -m simulator.simulator \
  --mode replay \
  --indoor-sensor-id 1 \
  --outdoor-sensor-id 2 \
  --seed 42 \
  --steps 288 \
  --start 2026-10-27T00:00:00Z
```

A successful first upload to an empty interval should return `201` for each new reading. Replaying the same data produces `409` duplicates, which the simulator counts and skips. For example, after the initial **72-reading** test, a complete replay of the same start time/seed should produce **1,620 new readings and 72 duplicates**, assuming no other overlapping records exist.

**Replay success and full database counts are not yet confirmed.**

### Verify stored data

From the repository root:

```bash
docker compose exec db psql -U air_quality_user -d air_quality_db
```

Then, in `psql`:

```sql
SELECT sensor_id, metric, COUNT(*) AS count
FROM readings
WHERE observed_at >= '2026-10-27T00:00:00Z'
  AND observed_at <  '2026-10-28T00:00:00Z'
GROUP BY sensor_id, metric
ORDER BY sensor_id, metric;
```

Use `\q` to exit `psql`. If other data was uploaded for that day, narrow the query to the intended sensor IDs before comparing counts.

## Testing

**Backend tests** require a running PostgreSQL development database:

```bash
cd backend
python -m pytest tests -v
```

**Simulator tests** do not require FastAPI or PostgreSQL:

```bash
# Run from repository root
python -m pytest simulator/tests -v
```

The Day 3 test file is designed to check total counts, metric/unit correctness, repeatability, five-minute spacing, indoor/outdoor scenario behaviour and the outage. The expected suite contains **10 tests**; **a passing run has not yet been confirmed**.

## Stopping and restarting the local database

From the project root:

```bash
docker compose stop     # Stop containers; keep persisted data
docker compose up -d    # Start them again
```

Avoid `docker compose down -v` unless you deliberately intend to **delete the database volume and all stored readings**.

## Requirements roadmap

The project specification identifies nine core requirements and two extensions. The present implementation concentrates on establishing a working data pipeline; it does **not** claim full completion of these requirements.

| Requirement | Planned functionality | Current state |
| --- | --- | --- |
| FR1 | Accounts, authentication, household isolation | Not implemented |
| FR2 | Create/view/rename/archive locations and sensors | Initial models and read endpoints; management incomplete |
| FR3 | Authenticated reading ingestion with validation | Local ingestion and validation; authentication outstanding |
| FR4 | Repeatable simulator and scenario replay | Preview verified; replay/database verification pending |
| FR5 | Latest readings, source labels and freshness | Latest stored-reading endpoint planned; stale status outstanding |
| FR6 | Historical charts and comparisons | Historical API retrieval; charts not implemented |
| FR7 | WHO PM2.5 guidance / eligible outdoor EPA-derived estimates | Not implemented |
| FR8 | Per-sensor PM2.5 threshold alerts | Not implemented |
| FR9 | Authenticated REST interface and versioned guidance | Initial REST/OpenAPI docs; authentication and guidance outstanding |
| FR10 | One-hour PM2.5 forecasting | Extension; not implemented |
| FR11 | Physical sensor adapter | Extension; not implemented |

### Guidance and data integrity requirements

The planned full application will compare supported **24-hour PM2.5 averages** with WHO guidance, and calculate eligible **outdoor-only** EPA-derived PM2.5 indices with documented averaging, coverage, source and rounding rules. It will not label indoor data as an official EPA AQI or claim regulatory compliance from WHO comparisons.

The specification also calls for household isolation, hashed passwords, HTTPS in deployment, preserved UTC timestamps, explicit missing-data gaps, source/version labels, threshold alerts and evidence-based acceptance checks. These remain future work.

## Next steps

1. Execute an end-to-end replay against the API and verify database counts/units/timestamps.
2. Confirm duplicate replay does not alter stored totals.
3. Run the API and simulator automated tests, recording actual results.
4. Add reading freshness/stale detection after three missed five-minute intervals.
5. Improve historical queries with date-range filtering and missing-data handling.
6. Review validation, error handling and test evidence.

## References

Project specification: *Home Air Quality Monitor — Fourth Year Project Report*, dated 9 October 2026.

- World Health Organization (2021), *WHO Global Air Quality Guidelines*: <https://www.who.int/publications/i/item/9789240034228>
- AirNow / US EPA, *AQI Basics*: <https://www.airnow.gov/aqi/aqi-basics/>
- AirNow / US EPA, *Technical Assistance Document for Reporting the Daily AQI*: <https://www.airnow.gov/publications/air-quality-index/technical-assistance-document-for-reporting-the-daily-aqi/>

These sources are part of the specification's future interpretation functionality; their methodology is **not yet implemented**.
