from pydantic import BaseModel, Field


class Category(BaseModel):
    id: int
    name: str


class Detection(BaseModel):
    bbox: list[float] = Field(..., min_length=4, max_length=4)
    score: float = Field(..., ge=0.0, le=1.0)


class DetectResponse(BaseModel):
    category_id: int
    category_name: str
    detections: list[Detection]
