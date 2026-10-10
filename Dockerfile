FROM python:3.14-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /bin/
LABEL Maintainer="Klaas Schoute"

WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && uv sync --locked --no-dev --no-cache \
    && apt-get purge -y --auto-remove git \
    && rm -rf /var/lib/apt/lists/*
COPY . /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["/app/.venv/bin/python"]
CMD ["main.py", "--help"]
