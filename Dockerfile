FROM python:3.14-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /bin/
LABEL Maintainer="Klaas Schoute"

WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-cache
COPY . /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["/app/.venv/bin/python"]
CMD ["main.py", "--help"]
