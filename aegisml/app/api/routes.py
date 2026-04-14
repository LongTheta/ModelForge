from __future__ import annotations

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.predict import router as predict_router

router = APIRouter()
router.include_router(health_router)
router.include_router(predict_router)
