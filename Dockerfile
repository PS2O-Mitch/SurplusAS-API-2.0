# Single-service Dockerfile for the Listing Service.
# When Compliance + Pricing land in Phase 4, split this into per-service
# Dockerfiles under services/<svc>/Dockerfile and a shared base.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install Python deps first so they cache across code-only changes.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App code (only what each service needs at runtime).
COPY shared/ /app/shared/
COPY services/ /app/services/
COPY static/ /app/static/

# Run as a non-root user.
RUN useradd -m -u 1001 surplus && chown -R surplus:surplus /app
USER surplus

ENV PORT=8080
EXPOSE 8080

CMD ["/bin/sh", "-c", "exec uvicorn services.listing.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
