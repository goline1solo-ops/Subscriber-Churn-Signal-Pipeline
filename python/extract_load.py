"""
Pulls real subscriber records (Kaggle), synthesizes a support-ticket-text
field the source data lacks, scores each for churn risk via an LLM, and
loads the result into Postgres.

Build order (see churn_signal_pipeline_project.md):
  1. generate_subscribers()  - real records + a synthesized support_ticket_text field
  2. score_churn_risk()      - call Ollama/Claude per record -> (churn_score, sentiment)
  3. load_to_postgres()      - insert into staging_subscriber_events
"""

import json
import os
import random

import kagglehub
import pandas as pd
import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

load_dotenv()

DATASET = "jayjoshi37/customer-subscription-churn-and-usage-patterns"
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "churn_signal")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "churn_user")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "changeme")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS staging_subscriber_events (
    subscriber_id INTEGER PRIMARY KEY,
    signup_date DATE,
    plan_tier TEXT,
    monthly_fee NUMERIC,
    avg_weekly_usage_hours NUMERIC,
    support_tickets INTEGER,
    payment_failures INTEGER,
    tenure_months INTEGER,
    last_login_days_ago INTEGER,
    churn TEXT,
    support_ticket_text TEXT,
    churn_score INTEGER,
    sentiment TEXT
);
"""

UPSERT_SQL = """
INSERT INTO staging_subscriber_events (
    subscriber_id, signup_date, plan_tier, monthly_fee, avg_weekly_usage_hours,
    support_tickets, payment_failures, tenure_months, last_login_days_ago,
    churn, support_ticket_text, churn_score, sentiment
) VALUES (
    %(subscriber_id)s, %(signup_date)s, %(plan_tier)s, %(monthly_fee)s,
    %(avg_weekly_usage_hours)s, %(support_tickets)s, %(payment_failures)s,
    %(tenure_months)s, %(last_login_days_ago)s, %(churn)s,
    %(support_ticket_text)s, %(churn_score)s, %(sentiment)s
)
ON CONFLICT (subscriber_id) DO UPDATE SET
    churn_score = EXCLUDED.churn_score,
    sentiment = EXCLUDED.sentiment;
"""

NEGATIVE_TICKETS = [
    "This app keeps crashing, I'm about to cancel.",
    "Not sure this is worth the price anymore.",
    "Payment failed again, this is getting frustrating.",
    "I haven't been able to log in properly in weeks.",
    "Thinking about switching to a competitor, too many issues.",
]

POSITIVE_TICKETS = [
    "Loving the new features, this is exactly what I needed!",
    "Great service, no complaints here.",
    "Really happy with the platform lately.",
    "Support team was fast and helpful, thanks!",
    "Everything's working smoothly for me.",
]

NEUTRAL_TICKETS = [
    "Just checking in on my subscription status.",
    "Question about upgrading my plan.",
    "Wanted to confirm my billing date.",
]


def _generate_ticket_text(record: dict) -> str:
    is_frustrated = record["payment_failures"] >= 2 or record["support_tickets"] >= 3
    is_happy = (
        record["payment_failures"] == 0
        and record["support_tickets"] <= 1
        and record["last_login_days_ago"] <= 7
    )

    if is_frustrated:
        return random.choice(NEGATIVE_TICKETS)
    if is_happy:
        return random.choice(POSITIVE_TICKETS)
    return random.choice(NEUTRAL_TICKETS)


def generate_subscribers(n: int = 200) -> list[dict]:
    path = kagglehub.dataset_download(DATASET)
    df = pd.read_csv(f"{path}/customer_subscription_churn_usage_patterns.csv")

    df = df.rename(columns={"user_id": "subscriber_id", "plan_type": "plan_tier"})

    if n < len(df):
        df = df.sample(n=n, random_state=42)

    records = df.to_dict(orient="records")
    for record in records:
        record["support_ticket_text"] = _generate_ticket_text(record)

    return records


def score_churn_risk(support_ticket_text: str) -> tuple[int, str]:
    prompt = (
        "You are scoring a customer support ticket for churn risk.\n"
        f'Ticket: "{support_ticket_text}"\n\n'
        "Respond with ONLY a JSON object, no other text, in this exact format:\n"
        '{"churn_score": <integer 1-10>, "sentiment": "<one word>"}\n'
        "churn_score: 1 means very unlikely to churn, 10 means very likely to churn."
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
    return result["churn_score"], result["sentiment"]


def load_to_postgres(records: list[dict]) -> None:
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


def main():
    records = generate_subscribers()
    for record in records:
        record["churn_score"], record["sentiment"] = score_churn_risk(
            record["support_ticket_text"]
        )
    load_to_postgres(records)


if __name__ == "__main__":
    main()
