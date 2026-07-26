"""
One-off script to download the Kaggle dataset and see what's actually in it
before deciding how to wire it into extract_load.py.

Run this natively (not in Docker):

    pip install kagglehub
    python python/explore_dataset.py

Delete or repurpose this once you've decided what columns you're keeping -
it's not part of the actual pipeline.
"""

import importlib
import os
import pandas as pd

try:
    kagglehub = importlib.import_module("kagglehub")
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing optional dependency 'kagglehub'. Install it with: pip install kagglehub"
    ) from exc

path = kagglehub.dataset_download(
    "jayjoshi37/customer-subscription-churn-and-usage-patterns"
)
print("Path to dataset files:", path)

files = os.listdir(path)
print("Files in dataset:", files)

csv_files = [f for f in files if f.endswith(".csv")]
if csv_files:
    df = pd.read_csv(os.path.join(path, csv_files[0]))
    print(f"\nShape: {df.shape}")
    print(f"\nColumns:\n{list(df.columns)}")
    print(f"\nFirst few rows:\n{df.head()}")
