"""
PATTERN: Extract -> AI-score -> Load. This is the "EL" of ELT - Transform
lives in dbt instead, as a separate step, run against data already sitting
in the warehouse. See GUIDE.md for why that split exists.

This file's CMD in Dockerfile makes it run automatically the instant the
`python` container starts (docker-compose up) - it is NOT something a user
needs to manually trigger. Any other one-off script you add to this folder
(exploration, analysis, connection tests) will NOT run automatically -
Docker only auto-runs whatever is named in the Dockerfile's CMD.
"""

import json
import os

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "app_db")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "app_user")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "changeme")

# TODO: replace with your actual staging table name/columns.
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS staging_events (
    record_id INTEGER PRIMARY KEY,
    -- ... your real columns here ...
    ai_score INTEGER,
    ai_label TEXT
);
"""

# ON CONFLICT DO UPDATE makes re-running this script safe/idempotent -
# no duplicate-key errors on a second run.
UPSERT_SQL = """
INSERT INTO staging_events (record_id, ai_score, ai_label)
VALUES (%(record_id)s, %(ai_score)s, %(ai_label)s)
ON CONFLICT (record_id) DO UPDATE SET
    ai_score = EXCLUDED.ai_score,
    ai_label = EXCLUDED.ai_label;
"""


def extract(n: int = 200) -> list[dict]:
    """
    TODO: pull/generate your raw records here (real dataset, API, synthetic
    data generator, etc). Must return a list of dicts, each with at least
    a unique `record_id` and whatever free-text field your AI step will
    read (e.g. `text_to_score`).

    GOTCHA if you condition synthetic text on a real ground-truth label
    (e.g. a real "churned"/"converted" outcome column): don't. That leaks
    the answer into your own AI step's input, and any correlation you find
    later is fake. Condition only on signals that exist BEFORE the outcome
    is known.
    """
    raise NotImplementedError


def score(text_to_score: str) -> tuple[int, str]:
    """
    Calls a local Ollama model, forcing structured JSON output so you get
    a real (score, label) tuple back instead of free-form prose you'd have
    to parse yourself.
    """
    prompt = (
        "You are scoring the following text.\n"
        f'Text: "{text_to_score}"\n\n'
        "Respond with ONLY a JSON object, no other text, in this exact format:\n"
        '{"score": <integer 1-10>, "label": "<one word>"}'
    )

    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        },
        timeout=30,
    )
    response.raise_for_status()

    result = json.loads(response.json()["response"])
    return result["score"], result["label"]


def load(records: list[dict]) -> None:
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            psycopg2.extras.execute_batch(cur, UPSERT_SQL, records)
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    records = extract()
    for record in records:
        record["ai_score"], record["ai_label"] = score(record["text_to_score"])
    load(records)


if __name__ == "__main__":
    main()
