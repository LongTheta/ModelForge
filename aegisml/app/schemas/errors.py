from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Stable machine-readable code")
    message: str = Field(..., description="Human-readable summary")
    detail: Any = Field(default=None, description="Extra context (e.g. validation issues)")


class ErrorResponse(BaseModel):
    error: ErrorDetail
