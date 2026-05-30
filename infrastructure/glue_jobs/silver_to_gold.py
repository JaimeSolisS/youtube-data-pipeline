import sys
import logging

from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame

from pyspark.sql import functions as F
from pyspark.sql.window import Window

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)

# ── Job Setup ────────────────────────────────────────────────────────────────
args = getResolvedOptions(sys.argv, [
    "JOB_NAME",
    "silver_database",
    "silver_statistics_table",
    "silver_reference_table",
    "gold_bucket",
    "gold_database",
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

SILVER_DB = args["silver_database"]
SILVER_STATS_TABLE = args["silver_statistics_table"]
SILVER_REF_TABLE = args["silver_reference_table"]
GOLD_BUCKET = args["gold_bucket"]
GOLD_DB = args["gold_database"]

logger.info(f"Silver DB: {SILVER_DB} ({SILVER_STATS_TABLE}, {SILVER_REF_TABLE})")
logger.info(f"Gold bucket: {GOLD_BUCKET}, Gold DB: {GOLD_DB}")


# ── Read Silver Statistics ────────────────────────────────────────────────────
logger.info(f"Reading {SILVER_DB}.{SILVER_STATS_TABLE}...")

stats_dyf = glueContext.create_dynamic_frame.from_catalog(
    database=SILVER_DB,
    table_name=SILVER_STATS_TABLE,
    transformation_ctx="stats",
)
stats_df = stats_dyf.toDF()
stats_count = stats_df.count()
logger.info(f"Statistics records: {stats_count}")

if stats_count == 0:
    logger.info("No records in silver statistics. Committing empty job.")
    job.commit()
    sys.exit(0)


# ── Read Reference Data + Build Category Lookup ───────────────────────────────
logger.info(f"Reading {SILVER_DB}.{SILVER_REF_TABLE} for category names...")

try:
    ref_dyf = glueContext.create_dynamic_frame.from_catalog(
        database=SILVER_DB,
        table_name=SILVER_REF_TABLE,
        transformation_ctx="ref",
    )
    ref_df = ref_dyf.toDF()

    category_lookup = None

    if "id" in ref_df.columns and "snippet.title" in ref_df.columns:
        category_lookup = ref_df.select(
            F.col("id").cast("long").alias("category_id"),
            F.col("`snippet.title`").alias("category_name"),
        ).dropDuplicates(["category_id"])

    elif "id" in ref_df.columns and "snippet_title" in ref_df.columns:
        category_lookup = ref_df.select(
            F.col("id").cast("long").alias("category_id"),
            F.col("snippet_title").alias("category_name"),
        ).dropDuplicates(["category_id"])

    else:
        logger.warning(
            "Could not find category title columns in reference data. "
            f"Columns found: {ref_df.columns}"
        )

    if category_lookup is not None:
        logger.info(f"Category lookup entries: {category_lookup.count()}")
        stats_df = stats_df.withColumn("category_id", F.col("category_id").cast("long"))
        stats_df = stats_df.join(F.broadcast(category_lookup), on="category_id", how="left")

except Exception as e:
    logger.warning(f"Could not load reference data: {e}. Proceeding without category names.")

if "category_name" not in stats_df.columns:
    stats_df = stats_df.withColumn("category_name", F.lit("Unknown"))
else:
    stats_df = stats_df.fillna("Unknown", subset=["category_name"])


# ══════════════════════════════════════════════════════════════════════════════
# GOLD TABLE 1: Trending Analytics (daily summaries per region)
# ══════════════════════════════════════════════════════════════════════════════
logger.info("Building Gold: trending_analytics...")

trending = stats_df.groupBy("region", "trending_date_parsed").agg(
    F.count("video_id").alias("total_videos"),
    F.sum("views").alias("total_views"),
    F.sum("likes").alias("total_likes"),
    F.sum("dislikes").alias("total_dislikes"),
    F.sum("comment_count").alias("total_comments"),
    F.avg("views").alias("avg_views_per_video"),
    F.avg("like_ratio").alias("avg_like_ratio"),
    F.avg("engagement_rate").alias("avg_engagement_rate"),
    F.max("views").alias("max_views"),
    F.countDistinct("channel_title").alias("unique_channels"),
    F.countDistinct("category_id").alias("unique_categories"),
)
trending = trending.withColumn("_aggregated_at", F.current_timestamp())

trending_path = f"s3://{GOLD_BUCKET}/youtube/gold_trending_analytics/"
trending_dyf = DynamicFrame.fromDF(trending, glueContext, "trending")

sink1 = glueContext.getSink(
    connection_type="s3",
    path=trending_path,
    enableUpdateCatalog=True,
    updateBehavior="UPDATE_IN_DATABASE",
    partitionKeys=["region"],
)
sink1.setCatalogInfo(catalogDatabase=GOLD_DB, catalogTableName="gold_trending_analytics")
sink1.setFormat("glueparquet", compression="snappy")
sink1.writeFrame(trending_dyf)
logger.info(f"  trending_analytics: {trending.count()} rows → {trending_path}")


# ══════════════════════════════════════════════════════════════════════════════
# GOLD TABLE 2: Channel Analytics
# ══════════════════════════════════════════════════════════════════════════════
logger.info("Building Gold: channel_analytics...")

channel = stats_df.groupBy("channel_title", "region").agg(
    F.countDistinct("video_id").alias("total_videos"),
    F.sum("views").alias("total_views"),
    F.sum("likes").alias("total_likes"),
    F.sum("comment_count").alias("total_comments"),
    F.avg("views").alias("avg_views_per_video"),
    F.avg("engagement_rate").alias("avg_engagement_rate"),
    F.max("views").alias("peak_views"),
    F.count("trending_date_parsed").alias("times_trending"),
    F.min("trending_date_parsed").alias("first_trending"),
    F.max("trending_date_parsed").alias("last_trending"),
    F.collect_set("category_name").alias("categories"),
)

window_rank = Window.partitionBy("region").orderBy(F.col("total_views").desc())
channel = channel.withColumn("rank_in_region", F.row_number().over(window_rank))
channel = channel.withColumn("_aggregated_at", F.current_timestamp())

channel_path = f"s3://{GOLD_BUCKET}/youtube/gold_channel_analytics/"
channel_dyf = DynamicFrame.fromDF(channel, glueContext, "channel")

sink2 = glueContext.getSink(
    connection_type="s3",
    path=channel_path,
    enableUpdateCatalog=True,
    updateBehavior="UPDATE_IN_DATABASE",
    partitionKeys=["region"],
)
sink2.setCatalogInfo(catalogDatabase=GOLD_DB, catalogTableName="gold_channel_analytics")
sink2.setFormat("glueparquet", compression="snappy")
sink2.writeFrame(channel_dyf)
logger.info(f"  channel_analytics: {channel.count()} rows → {channel_path}")


# ══════════════════════════════════════════════════════════════════════════════
# GOLD TABLE 3: Category Analytics (trend over time)
# ══════════════════════════════════════════════════════════════════════════════
logger.info("Building Gold: category_analytics...")

category = stats_df.groupBy("category_name", "category_id", "region", "trending_date_parsed").agg(
    F.count("video_id").alias("video_count"),
    F.sum("views").alias("total_views"),
    F.sum("likes").alias("total_likes"),
    F.sum("comment_count").alias("total_comments"),
    F.avg("engagement_rate").alias("avg_engagement_rate"),
    F.countDistinct("channel_title").alias("unique_channels"),
)

window_total = Window.partitionBy("region", "trending_date_parsed")
category = category.withColumn(
    "view_share_pct",
    F.round(F.col("total_views") / F.sum("total_views").over(window_total) * 100, 2),
)
category = category.withColumn("_aggregated_at", F.current_timestamp())

category_path = f"s3://{GOLD_BUCKET}/youtube/gold_category_analytics/"
category_dyf = DynamicFrame.fromDF(category, glueContext, "category")

sink3 = glueContext.getSink(
    connection_type="s3",
    path=category_path,
    enableUpdateCatalog=True,
    updateBehavior="UPDATE_IN_DATABASE",
    partitionKeys=["region"],
)
sink3.setCatalogInfo(catalogDatabase=GOLD_DB, catalogTableName="gold_category_analytics")
sink3.setFormat("glueparquet", compression="snappy")
sink3.writeFrame(category_dyf)
logger.info(f"  category_analytics: {category.count()} rows → {category_path}")

logger.info("Gold layer build complete.")
job.commit()
