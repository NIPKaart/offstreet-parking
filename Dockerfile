# BASE IMAGE
FROM python:3.9-slim-buster
LABEL Maintainer="Klaas Schoute"

# ADD SOME FILES
COPY ./requirements.txt ./app/
WORKDIR /app
RUN pip install -r requirements.txt

COPY . /app

ENTRYPOINT ["python"]
CMD ["__init__.py"]