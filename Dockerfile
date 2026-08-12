FROM python:3.13.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libjpeg62-turbo \
    libopenjp2-7 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/ .
RUN chmod +x scripts/deploy_build.sh scripts/deploy_start.sh \
    && DJANGO_DEBUG=false DJANGO_SECRET_KEY=build-only-not-used-at-runtime scripts/deploy_build.sh \
    && rm -f db.sqlite3

CMD ["scripts/deploy_start.sh"]
