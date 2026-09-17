
from pydantic import BaseModel


class Passenger(BaseModel):
    id: int
    origin: str
    destination: str
