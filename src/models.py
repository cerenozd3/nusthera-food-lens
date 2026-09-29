from pydantic import BaseModel, Field


class DetectedItem(BaseModel):
    """One food the vision model claims to see. Nutrition is not part of this schema."""

    name: str = Field(min_length=1)
    grams: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)


class VisionResponse(BaseModel):
    """Exact JSON contract from the assignment PDF."""

    items: list[DetectedItem]
    notes: str = ""
