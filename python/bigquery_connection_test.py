"""
One-off script to confirm `gcloud auth application-default login` is wired up
correctly: connects to BigQuery using your local Application Default
Credentials and runs a query against a free public dataset.

Run this natively (not in Docker) so it picks up the ADC file gcloud already
saved on your machine:

    pip install google-cloud-bigquery
    python bigquery_connection_test.py

Delete this file once you've confirmed the connection works - it's not part
of the actual pipeline.
"""

from google.cloud import bigquery

PROJECT_ID = "subscriber-churn-signal-pl"


def main():
    client = bigquery.Client(project=PROJECT_ID)

    query = """
        SELECT name, SUM(number) AS total
        FROM `bigquery-public-data.usa_names.usa_1910_2013`
        WHERE state = 'TX'
        GROUP BY name
        ORDER BY total DESC
        LIMIT 10
    """

    print(f"Querying BigQuery as project: {PROJECT_ID}\n")
    for row in client.query(query).result():
        print(f"{row.name:<15} {row.total}")


if __name__ == "__main__":
    main()
