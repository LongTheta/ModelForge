from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api import router
from app.deployment import get_deployment_meta, log_deployment_startup
from app.error_handlers import register_error_handlers
from app.inference import get_classifier
from app.observability import set_deployment_metadata, setup_http_metrics, setup_opentelemetry


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_classifier().ensure_loaded()
    meta = get_deployment_meta()
    set_deployment_metadata(meta)
    log_deployment_startup(meta)
    yield


app = FastAPI(
    title="AegisML",
    version=__version__,
    lifespan=lifespan,
)
register_error_handlers(app)
app.include_router(router)
setup_http_metrics(app)
setup_opentelemetry(app)
