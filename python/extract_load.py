"""
Generates synthetic subscriber records, scores each support-ticket text
for churn risk via an LLM, and loads the result into Postgres.

Build order (see churn_signal_pipeline_project.md):
  1. generate_subscribers()  - ~200 fake records w/ a support_ticket_text field
  2. score_churn_risk()      - call Ollama/Claude per record -> (churn_score, sentiment)
  3. load_to_postgres()      - insert into staging_subscriber_events
"""


def generate_subscribers(n: int = 200):
    raise NotImplementedError


def score_churn_risk(support_ticket_text: str):
    raise NotImplementedError


def load_to_postgres(records):
    raise NotImplementedError


def main():
    records = generate_subscribers()
    for record in records:
        record["churn_score"], record["sentiment"] = score_churn_risk(
            record["support_ticket_text"]
        )
    load_to_postgres(records)


if __name__ == "__main__":
    main()
