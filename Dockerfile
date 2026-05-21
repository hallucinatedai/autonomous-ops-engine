# Build stage
FROM python:3.11-alpine3.21@sha256:2028aa537a16aa0e455e330c4c30ef067ec18c47c7c1a1a9c5e27aa5263c4072 AS builder

WORKDIR /build

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir --prefix=/install .

# Runtime stage
FROM python:3.11-alpine3.21@sha256:2028aa537a16aa0e455e330c4c30ef067ec18c47c7c1a1a9c5e27aa5263c4072

WORKDIR /app

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY --from=builder /install /usr/local
COPY --chown=appuser:appuser src/ ./src/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8000/health || exit 1

CMD ["uvicorn", "ops_engine.api:app", "--host", "0.0.0.0", "--port", "8000"]
