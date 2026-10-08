FROM python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f AS builder

WORKDIR /build
COPY requirements.lock requirements-dev.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.lock \
    && pip install --no-cache-dir --find-links=/wheels -r requirements-dev.txt
COPY app app
COPY data data
COPY scripts scripts
COPY tests tests
RUN python scripts/build_index.py --output artifacts \
    && pytest -q \
    && python scripts/evaluate.py --artifact-dir artifacts

FROM python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ARTIFACT_DIR=/app/artifacts \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1

RUN groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY requirements.lock .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.lock \
    && rm -rf /wheels
COPY --from=builder --chown=10001:10001 /build/app app
COPY --from=builder --chown=10001:10001 /build/artifacts artifacts

USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
