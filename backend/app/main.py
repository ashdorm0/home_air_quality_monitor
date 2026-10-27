from fastapi import FastAPI, HTTPException

from app.database import check_database_connection

from app.routes import locations
from app.routes import sensors
from app.routes import readings


app = FastAPI(
    title="Home Air Quality Monitor API",
    description=(
        "REST API for the Home Air Quality Monitor "
        "capstone project."
    ),
    version="0.2.0",
)


app.include_router(locations.router)
app.include_router(sensors.router)
app.include_router(readings.router)


@app.get("/")
def root():
    return {
        "message": "Home Air Quality Monitor API",
        "version": "0.2.0",
    }


@app.get("/health")
def health_check():

    try:
        check_database_connection()

        return {
            "status": "healthy",
            "database": "connected",
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "disconnected",
            },
        )