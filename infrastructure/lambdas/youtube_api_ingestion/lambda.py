import csv
import io
import json
import os
import logging
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

import boto3

# ── Logging ──────────────────────────────────────────────────────────────────
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── AWS Clients ──────────────────────────────────────────────────────────────
s3_client = boto3.client("s3")
sns_client = boto3.client("sns")

# ── Config ───────────────────────────────────────────────────────────────────
API_KEY = os.environ["YOUTUBE_API_KEY"]
BUCKET = os.environ["S3_BUCKET_BRONZE"]
REGIONS = "US,FR,JP,MX".split(",")
SNS_TOPIC = os.environ.get("SNS_ALERT_TOPIC_ARN", "")
API_BASE = "https://www.googleapis.com/youtube/v3"
MAX_RESULTS = 50


def fetch_trending_videos(region_code: str) -> dict:
    params = urlencode({
        "part": "snippet,statistics,contentDetails",
        "chart": "mostPopular",
        "regionCode": region_code,
        "maxResults": MAX_RESULTS,
        "key": API_KEY,
    })
    url = f"{API_BASE}/videos?{params}"
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_video_categories(region_code: str) -> dict:
    params = urlencode({
        "part": "snippet",
        "regionCode": region_code,
        "key": API_KEY,
    })
    url = f"{API_BASE}/videoCategories?{params}"
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# region is omitted — it is encoded in the S3 partition path (region=xx/)
CSV_FIELDS = [
    "video_id", "trending_date", "title", "channel_title", "category_id",
    "publish_time", "tags", "views", "likes", "dislikes", "comment_count",
    "thumbnail_link", "comments_disabled", "ratings_disabled",
    "video_error_or_removed", "description",
]


def clean(text) -> str:
    """Strip newlines and carriage returns so the value stays on one CSV row."""
    return str(text or "").replace("\r", " ").replace("\n", " ").strip()


def flatten_video(item: dict, now: datetime) -> dict:
    s = item.get("snippet", {})
    stats = item.get("statistics", {})
    return {
        "video_id":               item.get("id", ""),
        "trending_date":          now.strftime("%Y-%m-%d"),
        "title":                  clean(s.get("title")),
        "channel_title":          clean(s.get("channelTitle")),
        "category_id":            s.get("categoryId", ""),
        "publish_time":           s.get("publishedAt", ""),
        "tags":                   "|".join(s.get("tags") or []),
        "views":                  stats.get("viewCount", "0"),
        "likes":                  stats.get("likeCount", "0"),
        "dislikes":               "0",
        "comment_count":          stats.get("commentCount", "0"),
        "thumbnail_link":         s.get("thumbnails", {}).get("default", {}).get("url", ""),
        "comments_disabled":      "False",
        "ratings_disabled":       "False",
        "video_error_or_removed": "False",
        "description":            clean(s.get("description")),
    }


def write_csv_to_s3(rows: list, bucket: str, key: str):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=buf.getvalue().encode("utf-8"),
        ContentType="text/csv",
        Metadata={"source": "youtube_data_api_v3"},
    )


def write_json_to_s3(data: dict, bucket: str, key: str):
    """Single JSON object — used for category reference data."""
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
        Metadata={"source": "youtube_data_api_v3"},
    )


def send_alert(subject: str, message: str):
    if SNS_TOPIC:
        sns_client.publish(TopicArn=SNS_TOPIC, Subject=subject[:100], Message=message)


def lambda_handler(event, context):
    now = datetime.now(timezone.utc)
    date_partition = now.strftime("%Y-%m-%d")
    hour_partition = now.strftime("%H")
    ingestion_id = now.strftime("%Y%m%d_%H%M%S")

    results = {"success": [], "failed": []}

    for region in REGIONS:
        region_lower = region.strip().lower()
        region_upper = region.strip().upper()
        logger.info(f"Processing region: {region_upper}")

        # ── Trending videos → CSV (one row per video) ────────────────────
        try:
            trending_data = fetch_trending_videos(region_upper)
            items = trending_data.get("items", [])
            rows = [flatten_video(item, now) for item in items]

            s3_key = (
                f"youtube/raw_statistics/"
                f"region={region_lower}/"
                f"date={date_partition}/"
                f"hour={hour_partition}/"
                f"{ingestion_id}.csv"
            )
            write_csv_to_s3(rows, BUCKET, s3_key)
            logger.info(f"  Wrote {len(rows)} videos → s3://{BUCKET}/{s3_key}")

        except (HTTPError, URLError) as e:
            logger.error(f"  API error for {region_upper} trending: {e}")
            results["failed"].append({"region": region_upper, "type": "trending", "error": str(e)})
            continue
        except Exception as e:
            logger.error(f"  Unexpected error for {region_upper} trending: {e}")
            results["failed"].append({"region": region_upper, "type": "trending", "error": str(e)})
            continue

        # ── Category reference data → JSON (raw API response) ────────────
        try:
            category_data = fetch_video_categories(region_upper)

            ref_key = (
                f"youtube/raw_statistics_reference_data/"
                f"region={region_lower}/"
                f"date={date_partition}/"
                f"{region_lower}_category_id.json"
            )
            write_json_to_s3(category_data, BUCKET, ref_key)
            logger.info(f"  Wrote {len(category_data.get('items', []))} categories → s3://{BUCKET}/{ref_key}")

        except (HTTPError, URLError) as e:
            logger.error(f"  API error for {region_upper} categories: {e}")
            results["failed"].append({"region": region_upper, "type": "categories", "error": str(e)})
            continue

        results["success"].append(region_upper)

    summary = (
        f"Ingestion {ingestion_id} complete. "
        f"Success: {len(results['success'])}/{len(REGIONS)} regions. "
        f"Failed: {len(results['failed'])}."
    )
    logger.info(summary)

    if results["failed"]:
        send_alert(
            subject=f"[YT Pipeline] Ingestion partial failure — {ingestion_id}",
            message=json.dumps(results, indent=2),
        )

    return {
        "statusCode": 200,
        "ingestion_id": ingestion_id,
        "results": results,
    }
