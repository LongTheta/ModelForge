# syntax=docker/dockerfile:1
# Build (context = aegisml/):  docker build -f docker/Dockerfile -t aegisml:local .

ARG PYTHON_VERSION=3.12

# Separate stage so the runtime image has no compiler toolchain; wheels land in the venv only.
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

WORKDIR /opt/aegisml

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependency metadata first for layer cache when application code churns.
COPY pyproject.toml ./

COPY app ./app
COPY src ./src

RUN python -m venv /opt/aegisml/venv \
    && /opt/aegisml/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
    && /opt/aegisml/venv/bin/pip install --no-cache-dir .

FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG UID=65532
ARG GID=65532
ARG GIT_COMMIT=unknown
ARG VERSION=0.2.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC \
    PATH="/opt/aegisml/venv/bin:$PATH" \
    AEGISML_GIT_COMMIT=${GIT_COMMIT} \
    AEGISML_HOST=0.0.0.0 \
    AEGISML_PORT=8080 \
    TMPDIR=/tmp/aegisml

LABEL org.opencontainers.image.title="aegisml" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

WORKDIR /opt/aegisml

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid "${GID}" aegisml \
    && useradd \
        --uid "${UID}" \
        --gid "${GID}" \
        --system \
        --shell /usr/sbin/nologin \
        --home-dir /opt/aegisml \
        --no-create-home \
        aegisml \
    && install -d -o aegisml -g aegisml -m 0750 /tmp/aegisml

COPY --from=builder /opt/aegisml/venv /opt/aegisml/venv

RUN chown -R "${UID}:${GID}" /opt/aegisml

USER aegisml

EXPOSE 8080

# Liveness: process up. Readiness is separate (/readyz) for orchestrators that support it.
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${AEGISML_PORT:-8080}/healthz" >/dev/null || exit 1

STOPSIGNAL SIGTERM

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/bin/sh", "-c", "exec uvicorn app.main:app --host \"${AEGISML_HOST}\" --port \"${AEGISML_PORT}\" --log-level \"${AEGISML_LOG_LEVEL:-info}\""]
