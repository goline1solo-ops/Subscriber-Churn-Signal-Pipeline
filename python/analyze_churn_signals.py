"""
One-off exploratory script: pull the loaded subscriber data into pandas and
look for actual statistical relationships with the real churn outcome,
rather than eyeballing averages/stddev by hand in SQL.

Not part of the automatic pipeline - same category as explore_dataset.py
and bigquery_connection_test.py, run manually, natively:

    pip install -r python/requirements.txt
    python python/analyze_churn_signals.py

Native run needs POSTGRES_HOST=localhost in .env (same swap as always -
remember to set it back to `postgres` before running docker-compose up).
"""

import os

import pandas as pd
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sqlalchemy import create_engine

load_dotenv()

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "churn_signal")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "churn_user")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "changeme")

FEATURES = [
    "avg_weekly_usage_hours",
    "support_tickets",
    "payment_failures",
    "tenure_months",
    "last_login_days_ago",
    "churn_score",
]


def load_data() -> pd.DataFrame:
    engine = create_engine(
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    df = pd.read_sql("SELECT * FROM staging_subscriber_events", engine)
    df["churned"] = (df["churn"] == "Yes").astype(int)
    return df


def print_correlations(df: pd.DataFrame) -> None:
    print("Correlation of each signal with the real churn outcome:\n")
    correlations = df[FEATURES + ["churned"]].corr()["churned"].drop("churned")
    print(correlations.sort_values(key=abs, ascending=False))
    print()


def print_feature_importances(df: pd.DataFrame) -> None:
    model = RandomForestClassifier(n_estimators=200, random_state=42)
    model.fit(df[FEATURES], df["churned"])

    importances = pd.Series(model.feature_importances_, index=FEATURES)
    print("Random forest feature importances (predicting real churn):\n")
    print(importances.sort_values(ascending=False))
    print()


def print_llm_score_validation(df: pd.DataFrame) -> None:
    correlation = df["churn_score"].corr(df["churned"])
    print(f"LLM churn_score vs. real churn outcome correlation: {correlation:.3f}")


def main() -> None:
    df = load_data()
    print_correlations(df)
    print_feature_importances(df)
    print_llm_score_validation(df)


if __name__ == "__main__":
    main()
