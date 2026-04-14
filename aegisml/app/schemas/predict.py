from pydantic import BaseModel, Field, field_validator


class PredictRequest(BaseModel):
    text: str = Field(..., description="Input text to classify.")

    @field_validator("text")
    @classmethod
    def strip_nonempty_bounded(cls, v: str) -> str:
        t = v.strip()
        if not t:
            raise ValueError("text must contain non-whitespace characters")
        if len(t) > 8000:
            raise ValueError("text must be at most 8000 characters after trimming")
        return t


class PredictResponse(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    scores: dict[str, float]
    model_version: str
