from sqlalchemy import select

from app.database import SessionLocal
from app.models import Location, Sensor


def seed_database():

    with SessionLocal() as db:

        locations = [
            ("Living Room", "indoor"),
            ("Garden", "outdoor"),
        ]

        for name, placement in locations:

            statement = select(Location).where(
                Location.name == name,
                Location.placement == placement,
                Location.is_archived.is_(False),
            )

            location = db.scalar(statement)

            if location is None:

                location = Location(
                    name=name,
                    placement=placement,
                )

                db.add(location)
                db.flush()

            sensor_name = f"{name} Sensor"

            sensor_statement = select(Sensor).where(
                Sensor.name == sensor_name,
                Sensor.location_id == location.id,
                Sensor.is_archived.is_(False),
            )

            sensor = db.scalar(sensor_statement)

            if sensor is None:

                sensor = Sensor(
                    name=sensor_name,
                    location_id=location.id,
                    source_type="simulated",
                )

                db.add(sensor)

        db.commit()

    print("Development locations and sensors are ready.")


if __name__ == "__main__":
    seed_database()