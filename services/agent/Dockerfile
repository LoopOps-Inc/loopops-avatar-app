# syntax=docker/dockerfile:1.7
# Multi-stage, non-root, reproducible. One image serves every role
# (`serve --role agent|suitability|guardrail|audit|transaction`).
#
# Why not gcr.io/distroless/python3-debian12 (the docs' hardening target)?
# That base ships Python 3.11 and this service is pinned to 3.12 (ADR-0004,
# pyproject `requires-python`). Running 3.12-compiled wheels on 3.11 is not an
# option. The runtime below is python:3.12-slim-bookworm with the same posture
# (non-root uid 65532, no package manager use at runtime, read-only root fs via
# the orchestrator, dropped capabilities, seccomp in the k8s manifests).
# To move to a true distroless base once one ships Python 3.12, replace the
# runtime FROM with e.g. `cgr.dev/chainguard/python:3.12` (pin a digest) and
# drop the `apt-get` lines; nothing else in this file changes.

FROM python:3.12-slim-bookworm AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /build
COPY pyproject.toml README.md alembic.ini ./
COPY src ./src
COPY prompts ./prompts
COPY migrations ./migrations
# Runtime deps only (no [dev]); installed into /deps and copied verbatim.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /usr/local/bin/python3 --target /deps --no-cache . \
    && find /deps -name "*.pyc" -delete \
    && find /deps -name "__pycache__" -type d -prune -exec rm -rf {} +

FROM python:3.12-slim-bookworm AS runtime
LABEL org.opencontainers.image.title="actinver-agent" \
      org.opencontainers.image.description="Actinver AI Advisor backend (bff, orchestrator, broker, voice, controls)" \
      org.opencontainers.image.source="https://github.com/LoopOps-Inc/loopops-avatar-app"
ENV PYTHONPATH=/deps \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PROMPTS_DIR=/app/prompts \
    HOME=/tmp
# Remove pip/setuptools from the runtime so nothing can install at run time.
RUN python -m pip uninstall -y pip setuptools wheel >/dev/null 2>&1 || true \
    && rm -rf /root/.cache \
    && mkdir -p /app \
    && chown -R 65532:65532 /app
COPY --from=builder --chown=65532:65532 /deps /deps
COPY --from=builder --chown=65532:65532 /build/prompts /app/prompts
COPY --from=builder --chown=65532:65532 /build/migrations /app/migrations
COPY --from=builder --chown=65532:65532 /build/alembic.ini /app/alembic.ini
WORKDIR /app
USER 65532:65532
EXPOSE 8443
# Liveness/readiness are Kubernetes probes (/healthz, /readyz); no HEALTHCHECK.
ENTRYPOINT ["python", "-m", "actinver_agent.cli"]
CMD ["serve", "--role", "agent", "--port", "8443"]
