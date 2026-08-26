ARG BUILD_ARCH=aarch64
ARG BUILD_VERSION=0.8.1

FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

ARG BUILD_ARCH
FROM ghcr.io/home-assistant/${BUILD_ARCH}-base-python:3.12-alpine3.20

ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="${BUILD_ARCH}" \
  io.hass.name="HealthHub" \
  io.hass.description="Personal nutrition, activity, goals and progress tracking for Home Assistant" \
  io.hass.url="https://github.com/stunwill/healthhub-home-assistant"

ENV HEALTHHUB_VERSION="${BUILD_VERSION}" \
    HEALTHHUB_DATA_DIR="/data/healthhub" \
    HEALTHHUB_STATIC_DIR="/app/static" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache tesseract-ocr tesseract-ocr-data-eng

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY --from=frontend /frontend/dist ./static
COPY run.sh /run.sh
RUN chmod a+x /run.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8098/api/v1/health >/dev/null || exit 1

CMD ["/run.sh"]
