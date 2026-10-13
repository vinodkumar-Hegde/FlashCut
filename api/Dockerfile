FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y \
       --no-install-recommends \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install \
    --no-cache-dir \
    --upgrade pip \
    && pip install \
       --no-cache-dir \
       -r requirements.txt

RUN addgroup \
      --system \
      app \
    && adduser \
      --system \
      --ingroup app \
      app

COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

RUN chown -R app:app /app

USER app

EXPOSE 5001

HEALTHCHECK \
  --interval=30s \
  --timeout=5s \
  --start-period=10s \
  --retries=3 \
  CMD python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5001/health/live', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5001"]
