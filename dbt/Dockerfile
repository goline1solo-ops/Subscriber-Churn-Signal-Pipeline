FROM python:3.11-slim

WORKDIR /usr/app
ENV DBT_PROFILES_DIR=/usr/app

RUN pip install --no-cache-dir dbt-postgres

COPY . .

CMD ["dbt", "run"]
