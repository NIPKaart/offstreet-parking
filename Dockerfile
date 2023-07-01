# BASE IMAGE
FROM python:3.11-slim-buster
LABEL Maintainer="Klaas Schoute"

COPY . /app
WORKDIR /app

# Install poetry and dependencies
RUN pip install poetry
RUN poetry config virtualenvs.create false
RUN poetry install --with cities --without dev

ENTRYPOINT ["python"]
CMD ["main.py"]
