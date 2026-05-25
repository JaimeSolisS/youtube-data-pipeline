import json
import os
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import boto3
import awswrangler as wr
import pandas as pd


# ── Config ───────────────────────────────────────────────────────────────────
SILVER_BUCKET = os.environ["S3_BUCKET_SILVER"]
SILVER_PATH = f"s3://{SILVER_BUCKET}/youtube/reference_data/"

s3_client = boto3.client("s3")


def read_json_from_s3(bucket: str, key: str) -> dict:
    """
    Read raw JSON from S3 using boto3 instead of awswrangler.
    awswrangler.s3.read_json() fails on the Kaggle/YouTube category JSON
    because it has mixed types (strings + nested arrays), which pandas
    can't parse directly into a DataFrame.
    """
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read().decode("utf-8")
    return json.loads(content)


def validate_category_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and clean the category reference data.
    Returns cleaned DataFrame or raises ValueError.
    """
    if df.empty:
        raise ValueError("Empty DataFrame — no category items found")

    required_cols = {"id", "snippet.title"}
    actual_cols = set(df.columns)
    missing = required_cols - actual_cols
    if missing:
        # Try alternate column names from different API versions
        print(f"Missing expected columns: {missing}. Available: {actual_cols}")

    # Drop duplicate categories (same id)
    before = len(df)
    if "id" in df.columns:
        df = df.drop_duplicates(subset=["id"], keep="last")
    after = len(df)
    if before != after:
        print(f"  Removed {before - after} duplicate categories")

    return df


def lambda_handler(event, context):
    """Process S3 event for new JSON reference files."""

    # Handle both direct S3 events and EventBridge-wrapped events
    records = event.get("Records", [])
    if not records:
        # Could be invoked directly by Step Functions
        records = [event] if "s3" in event else []

    processed = []
    errors = []

    for record in records:
        try:
            s3_info = record["s3"]
            bucket = s3_info["bucket"]["name"]
            key = unquote_plus(s3_info["object"]["key"])

            print(f"Processing: s3://{bucket}/{key}")

            # ── Read raw JSON ────────────────────────────────────────────
            # We use boto3 + json.loads instead of wr.s3.read_json() because
            # the category JSON has mixed types (strings like "kind"/"etag"
            # alongside a nested "items" array) which causes pandas to fail
            # with: "Mixing dicts with non-Series may lead to ambiguous ordering"
            raw_data = read_json_from_s3(bucket, key)

            # The YouTube/Kaggle JSON has { "kind": "...", "items": [...] }
            # We only care about the items array
            if "items" in raw_data and isinstance(raw_data["items"], list):
                df = pd.json_normalize(raw_data["items"])
            else:
                # Fallback: try to normalize the entire object
                df = pd.json_normalize(raw_data)

            print(f"  Raw shape: {df.shape}")

            # ── Validate ─────────────────────────────────────────────────
            df = validate_category_data(df)

            # ── Add metadata columns ─────────────────────────────────────
            df["_ingestion_timestamp"] = datetime.now(timezone.utc).isoformat()
            df["_source_file"] = key

            # Extract region from the S3 key (e.g., region=US)
            region = "unknown"
            for part in key.split("/"):
                if part.startswith("region="):
                    region = part.split("=")[1]
                    break
            df["region"] = region

            print(f"  Clean shape: {df.shape}, region: {region}")

            processed.append({"key": key, "region": region, "rows": len(df)})

        except Exception as e:
            print(f"Error processing record: {e}", exc_info=True)
            errors.append({"key": key if "key" in dir() else "unknown", "error": str(e)})

    return {
        "statusCode": 200,
        "processed": processed,
        "errors": errors,
    }