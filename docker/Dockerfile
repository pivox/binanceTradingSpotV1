FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/

RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

COPY . /app

CMD ["python", "-m", "tradebot.apps.temporal_worker_main"]
