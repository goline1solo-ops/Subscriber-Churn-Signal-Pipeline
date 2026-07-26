"""
One-off end-to-end smoke test: generate a few records, score them, load them.
Delete once the full pipeline is confirmed working - not part of the actual
pipeline.
"""

from extract_load import generate_subscribers, load_to_postgres, score_churn_risk

records = generate_subscribers(n=5)
for r in records:
    r["churn_score"], r["sentiment"] = score_churn_risk(r["support_ticket_text"])

load_to_postgres(records)
print(f"Loaded {len(records)} records")
