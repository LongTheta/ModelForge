"""Deployment identity for logs, metrics labels, and tracing resource attributes."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from app import __version__

logger = logging.getLogger("aegisml")


@dataclass(frozen=True)
class DeploymentMeta:
    """Fields used for metrics Info labels, structured logs, and OTel resource (where set)."""

    version: str
    environment: str
    git_commit: str
    git_commit_full: str
    pod_name: str
    pod_namespace: str


def _short_sha(raw: str) -> str:
    if not raw:
        return "unknown"
    return raw[:7] if len(raw) >= 7 else raw


def get_deployment_meta() -> DeploymentMeta:
    ver = os.getenv("AEGISML_VERSION") or __version__
    env = os.getenv("AEGISML_ENVIRONMENT") or os.getenv("AEGISML_DEPLOYMENT", "local")
    from_ci = (
        os.getenv("AEGISML_GIT_COMMIT")
        or os.getenv("CI_COMMIT_SHORT_SHA")
        or os.getenv("GITHUB_SHA")
        or ""
    )
    full = (os.getenv("AEGISML_GIT_COMMIT_FULL") or from_ci or "unknown").strip() or "unknown"
    short = _short_sha(from_ci) if from_ci else (_short_sha(full) if full != "unknown" else "unknown")
    pod = os.getenv("POD_NAME", "")
    ns = os.getenv("POD_NAMESPACE", "")
    return DeploymentMeta(
        version=ver,
        environment=env,
        git_commit=short,
        git_commit_full=full,
        pod_name=pod,
        pod_namespace=ns,
    )


def log_deployment_startup(meta: DeploymentMeta) -> None:
    payload = {
        "event": "service_start",
        "version": meta.version,
        "environment": meta.environment,
        "git_commit": meta.git_commit,
        "git_commit_full": meta.git_commit_full,
        "pod_name": meta.pod_name or None,
        "pod_namespace": meta.pod_namespace or None,
    }
    logger.info(json.dumps({k: v for k, v in payload.items() if v is not None}))
