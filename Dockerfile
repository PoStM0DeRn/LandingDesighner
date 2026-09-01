# syntax=docker/dockerfile:1

########## Stage 1: build the frontend ##########
FROM node:20-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

########## Stage 2: runtime (backend + built frontend + node for tailwind) ##########
# Same Debian base as the node stage, so the node binary copied below runs natively.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STORAGE_DIR=/data \
    SERVE_FRONTEND=true

WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN python -m pip install -r requirements.txt

# Chromium for headless landing screenshots (thumbnails)
RUN python -m playwright install --with-deps chromium

# Node runtime from the build stage — enables the real Tailwind build
# (npx tailwindcss@3.4) inside the container instead of the Play CDN fallback.
COPY --from=frontend-build /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend-build /usr/local/bin/npm /usr/local/bin/npm
COPY --from=frontend-build /usr/local/bin/npx /usr/local/bin/npx
COPY --from=frontend-build /usr/local/lib/node_modules /usr/local/lib/node_modules
# Warm the npx cache so runtime Tailwind builds need no downloads.
RUN npx --yes tailwindcss@3.4 --version

COPY backend/ ./
COPY templates/ /app/templates/
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://127.0.0.1:8000/api/health', timeout=8).status_code == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
