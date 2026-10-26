from fastapi import FastAPI, HTTPException

from app.database import check_database_connection


app = FastAPI(
    title="Home Air Quality Monitor API",
    description=(
        "Backend API for the Home Air Quality Monitor "
        "capstone project."
    ),
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "message": "Home Air Quality Monitor API",
        "version": "0.1.0"
    }


@app.get("/health")
def health_check():
    """
    Check API and database health.
    """

    try:
        check_database_connection()

        return {
            "status": "healthy",
            "database": "connected"
        }

    except Exception:

        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "disconnected"
            }
        )