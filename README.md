# Subscriber Churn Signal Pipeline

A containerized ELT pipeline with an AI enrichment step: synthetic subscriber
events + support-ticket text are extracted, scored for churn risk by an LLM,
loaded into Postgres, and modeled with dbt into a subscriber-risk table.

## Structure

- `python/` — generates synthetic subscriber data, scores support-ticket
  text for churn risk via an LLM, loads into Postgres (`extract_load.py`)
- `dbt/` — models staging data into `subscriber_risk_model` (risk tiers,
  at-risk flags)
- `docker-compose.yml` — wires up python, postgres, and dbt as one stack

## Setup

```bash
cp .env.example .env   # fill in real values
docker-compose up -d
docker-compose logs -f
```

Then connect to the Postgres container (`psql` or DBeaver) to inspect the
final `subscriber_risk_model` table.

## Status

Scaffold only — see `churn_signal_pipeline_project.md` for the full build
plan and current step.
