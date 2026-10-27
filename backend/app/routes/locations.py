from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Location
from app.schemas import LocationResponse


router = APIRouter(
    prefix="/locations",
    tags=["Locations"],
)


@router.get(
    "",
    response_model=list[LocationResponse],
)
def get_locations(
    db: Annotated[Session, Depends(get_db)],
):
    """
    Retrieve all active locations.
    """

    statement = (
        select(Location)
        .where(Location.is_archived.is_(False))
        .order_by(Location.id)
    )

    locations = db.scalars(statement).all()

    return locations