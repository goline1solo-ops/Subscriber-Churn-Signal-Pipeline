# Containerized ELT + AI Enrichment - Starter Template

A reusable scaffold: Python (extract + AI-score + load) -> Postgres (staging)
-> dbt (transform into a final model), all containerized and wired together
via Docker Compose.

**Start here: [GUIDE.md](GUIDE.md)** - it has everything: the architecture,
every recurring gotcha from building this pattern the first time, a T-SQL to
Postgres cheat sheet, a debugging playbook, and a "coming back after months
away" checklist.

## Quick start

```bash
cp .env.example .env        # fill in real values
docker-compose up -d --build
docker-compose logs -f python
```

Then connect (DBeaver, psql, or `docker exec <postgres_container> psql -U <user> -d <db>`)
to inspect the results, and run `docker-compose run --rm dbt dbt run` once
your model logic in `dbt/models/` is filled in.

## Structure

```
docker-compose.yml       # wires postgres + python + dbt together
.env.example             # connection config template (see GUIDE.md - localhost gotcha)
python/
  Dockerfile
  requirements.txt
  extract_load.py        # extract -> AI-score -> load skeleton
dbt/
  Dockerfile
  dbt_project.yml
  profiles.yml            # connection info for dbt (env_var()-based)
  models/
    sources.yml           # declares the raw staging table
    example_model.sql      # CTE-based transform skeleton
```
