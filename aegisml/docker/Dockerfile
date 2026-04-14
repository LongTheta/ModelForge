# syntax=docker/dockerfile:1
# Build from repo: docker build -f aegisml/docker/Dockerfile -t aegisml:local aegisml
# Kaniko (GitLab): context = aegisml/, same Dockerfile path.

ARG PYTHON_VERSION=3.12

# -----------------------------------------------------------------------------
# Builder: install app + dependencies into a dedicated venv (no compiler in final).
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

WORKDIR /opt/aegisml

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt pyproject.toml ./
COPY app ./app
COPY src ./src

RUN python -m venv /opt/aegisml/venv \
    && /opt/aegisml/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
    && /opt/aegisml/venv/bin/pip install --no-cache-dir .

# -----------------------------------------------------------------------------
# Runtime: minimal OS packages, non-root, tini, healthcheck.
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG UID=65532
ARG GID=65532
ARG GIT_COMMIT=unknown
ARG VERSION=0.2.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC \
    PYTHONHASHSEED=random \
    PATH="/opt/aegisml/venv/bin:$PATH" \
    AEGISML_GIT_COMMIT=${GIT_COMMIT} \
    AEGISML_HOST=0.0.0.0 \
    AEGISML_PORT=8080 \
    TMPDIR=/tmp/aegisml

LABEL org.opencontainers.image.title="AegisML Inference" \
      org.opencontainers.image.description="FastAPI ML inference service (governed delivery MVP)" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

WORKDIR /opt/aegisml

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tini ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid "${GID}" aegisml \
    && useradd \
        --uid "${UID}" \
        --gid "${GID}" \
        --shell /usr/sbin/nologin \
        --home-dir /opt/aegisml \
        --no-create-home \
        aegisml \
    && install -d -o aegisml -g aegisml -m 0750 /tmp/aegisml

COPY --from=builder /opt/aegisml/venv /opt/aegisml/venv

RUN chown -R aegisml:aegisml /opt/aegisml

USER aegisml

EXPOSE 8080

# Model warms in lifespan; allow startup before marking unhealthy.
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
    CMD /bin/sh -c 'curl -fsS "http://127.0.0.1:${AEGISML_PORT:-8080}/healthz" >/dev/null || exit 1'

STOPSIGNAL SIGTERM

ENTRYPOINT ["/usr/bin/tini", "--"]
# Shell so AEGISML_* env overrides work the same as Kubernetes ConfigMaps.
CMD ["/bin/sh", "-c", "exec uvicorn app.main:app --host \"${AEGISML_HOST}\" --port \"${AEGISML_PORT}\" --log-level \"${AEGISML_LOG_LEVEL:-info}\""]
