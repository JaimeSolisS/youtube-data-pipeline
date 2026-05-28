import sys
import logging
from datetime import datetime

from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame

from pyspark.sql import functions as F
from pyspark.sql.types import (
    LongType,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Job Setup ────────────────────────────────────────────────────────────────
args = getResolvedOptions(sys.argv, [
    "JOB_NAME",
    "bronze_bucket",
    "bronze_database",
    "bronze_table",
    "silver_bucket",
    "silver_database",
    "silver_table",
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# ── Config ───────────────────────────────────────────────────────────────────
BRONZE_BUCKET = args["bronze_bucket"]
BRONZE_DB = args["bronze_database"]
BRONZE_TABLE = args["bronze_table"]
SILVER_BUCKET = args["silver_bucket"]
SILVER_DB = args["silver_database"]
SILVER_TABLE = args["silver_table"]
SILVER_PATH = f"s3://{SILVER_BUCKET}/youtube/statistics/"
BRONZE_BASE = f"s3://{BRONZE_BUCKET}/youtube/raw_statistics/"
REGIONS = ["us", "fr", "jp", "mx"]

logger.info(f"Bronze: {BRONZE_BASE}")
logger.info(f"Silver: {SILVER_DB}.{SILVER_TABLE} → {SILVER_PATH}")


# ── Step 1: Read from Bronze ────────────────────────────────────────────────
logger.info("Reading from Bronze S3 directly...")

# Read JSON files directly, bypassing catalog schema enforcement.
# basePath lets Spark detect region=/ date=/ hour=/ as partition columns.
region_paths = [f"{BRONZE_BASE}region={r}/" for r in REGIONS]
df = spark.read.option("basePath", BRONZE_BASE).json(region_paths)

initial_count = df.count()
logger.info(f"Bronze records read: {initial_count}")
logger.info(f"Schema: {df.dtypes}")

if initial_count == 0:
    logger.info("No new records to process. Committing empty job.")
else:
    # ── Step 2: Schema Enforcement ──────────────────────────────────────────
    logger.info("Enforcing schema and casting types...")
    logger.info(f"Columns: {df.columns}")

    columns = set(df.columns)

    if "snippet" in columns and "statistics" in columns:
        # YouTube API JSON format — Glue reads nested JSON as structs
        logger.info("Detected YouTube API nested struct format — flattening...")
        df = df.select(
            F.col("id").alias("video_id"),
            F.lit(datetime.utcnow().strftime("%y.%d.%m")).alias("trending_date"),
            F.col("snippet.title").alias("title"),
            F.col("snippet.channelTitle").alias("channel_title"),
            F.col("snippet.categoryId").cast(LongType()).alias("category_id"),
            F.col("snippet.publishedAt").alias("publish_time"),
            F.concat_ws("|", F.col("snippet.tags")).alias("tags"),
            F.col("statistics.viewCount").cast(LongType()).alias("views"),
            F.col("statistics.likeCount").cast(LongType()).alias("likes"),
            F.lit(0).cast(LongType()).alias("dislikes"),
            F.col("statistics.commentCount").cast(LongType()).alias("comment_count"),
            F.col("snippet.thumbnails.default.url").alias("thumbnail_link"),
            F.lit(False).alias("comments_disabled"),
            F.lit(False).alias("ratings_disabled"),
            F.lit(False).alias("video_error_or_removed"),
            F.col("snippet.description").alias("description"),
            F.col("region"),
        )
    

    # ── Step 3: Data Cleansing ──────────────────────────────────────────────
    logger.info("Cleansing data...")

    # Remove records where video_id is null (corrupt rows)
    df = df.filter(F.col("video_id").isNotNull())

    # Standardize region codes to lower
    df = df.withColumn("region", F.lower(F.trim(F.col("region"))))

    # Parse trending_date from Kaggle format (YY.DD.MM) to proper date
    df = df.withColumn(
        "trending_date_parsed",
        F.when(
            F.col("trending_date").rlike(r"^\d{2}\.\d{2}\.\d{2}$"),
            F.to_date(F.col("trending_date"), "yy.dd.MM")
        ).otherwise(
            F.to_date(F.col("trending_date"))
        )
    )

    # Fill nulls for numeric columns with 0
    numeric_cols = ["views", "likes", "dislikes", "comment_count"]
    for col_name in numeric_cols:
        df = df.withColumn(col_name, F.coalesce(F.col(col_name), F.lit(0)))

    # Add derived columns
    df = df.withColumn("like_ratio",
        F.when(
            (F.col("views") > 0),
            F.round(F.col("likes") / F.col("views") * 100, 4)
        ).otherwise(0.0)
    )
    df = df.withColumn("engagement_rate",
        F.when(
            (F.col("views") > 0),
            F.round((F.col("likes") + F.col("dislikes") + F.col("comment_count")) / F.col("views") * 100, 4)
        ).otherwise(0.0)
    )

    # Add processing metadata
    df = df.withColumn("_processed_at", F.current_timestamp())
    df = df.withColumn("_job_name", F.lit(args["JOB_NAME"]))


    # ── Step 4: Deduplication ───────────────────────────────────────────────
    logger.info("Deduplicating...")

    # Keep the latest record per video_id + region + trending_date
    from pyspark.sql.window import Window

    window = Window.partitionBy("video_id", "region", "trending_date_parsed") \
        .orderBy(F.col("_processed_at").desc())

    df = df.withColumn("_row_num", F.row_number().over(window)) \
        .filter(F.col("_row_num") == 1) \
        .drop("_row_num")

    clean_count = df.count()
    logger.info(f"After cleansing & dedup: {clean_count} records (removed {initial_count - clean_count})")


    # ── Step 5: Data Quality Checks ─────────────────────────────────────────
    logger.info("Running data quality checks...")

    null_counts = {}
    for col_name in ["video_id", "title", "channel_title", "views"]:
        null_count = df.filter(F.col(col_name).isNull()).count()
        null_counts[col_name] = null_count
        if null_count > 0:
            logger.warning(f"  DQ WARNING: {col_name} has {null_count} null values")

    negative_views = df.filter(F.col("views") < 0).count()
    if negative_views > 0:
        logger.warning(f"  DQ WARNING: {negative_views} records with negative views")

    logger.info(f"  DQ check complete. Null counts: {null_counts}")


    # ── Step 6: Write to Silver Layer ───────────────────────────────────────
    logger.info(f"Writing to Silver: {SILVER_PATH}")

    # Convert back to DynamicFrame for Glue-native write
    dynamic_frame = DynamicFrame.fromDF(df, glueContext, "silver_statistics")

    sink = glueContext.getSink(
        connection_type="s3",
        path=SILVER_PATH,
        enableUpdateCatalog=True,
        updateBehavior="UPDATE_IN_DATABASE",
        partitionKeys=["region"],
    )
    sink.setCatalogInfo(catalogDatabase=SILVER_DB, catalogTableName=SILVER_TABLE)
    sink.setFormat("glueparquet", compression="snappy")
    sink.writeFrame(dynamic_frame)

    logger.info(f"Silver write complete. {clean_count} records written.")

job.commit()