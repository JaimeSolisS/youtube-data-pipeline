# YouTube Data Pipeline

A serverless medallion-architecture data pipeline on AWS that ingests YouTube trending data, transforms it through bronze → silver → gold layers, runs data quality checks, and aggregates analytics — orchestrated end-to-end by Step Functions on an 8-hour schedule.

## Architecture

```
YouTube API
    │
    ▼
Lambda (youtube_api_ingestion)
    ├── Trending videos  → S3 Bronze (CSV, partitioned by region/date/hour)
    └── Category data   → S3 Bronze (JSON, partitioned by region/date)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
    Lambda (json_to_parquet)       Glue Job (bronze → silver)
    Category JSON → Parquet        CSV → cleaned Parquet
    S3 Silver                      S3 Silver
              └───────────────┬───────────────┘
                              ▼
                   Lambda (data_quality_checks)
                   Athena queries on silver tables
                              │
                    ┌─────────┴─────────┐
                  PASS                FAIL
                    │                  │
                    ▼                  ▼
          Glue Job (silver → gold)   SNS alert
          3 aggregation tables
          S3 Gold

All steps orchestrated by AWS Step Functions, triggered every 8 hours via EventBridge Scheduler.
```

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.3.0
- AWS account with an IAM user that has programmatic access
- YouTube Data API v3 key — create one at [console.cloud.google.com](https://console.cloud.google.com) under APIs & Services → Credentials

### Configure AWS credentials

**Option A — default profile**

```bash
aws configure
```

**Option B — named profile**

```bash
aws configure --profile your-username
export AWS_PROFILE=your-username
```

Credentials are stored in `~/.aws/credentials` and config in `~/.aws/config`.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/JaimeSolisS/youtube-data-pipeline.git
cd youtube-data-pipeline
```

### 2. Configure Terraform

```bash
cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars
```

Edit `infrastructure/terraform.tfvars` — S3 bucket names must be globally unique, so add a personal suffix:

```hcl
project_name = "yt-data-pipeline"
aws_region   = "us-east-1"

s3_bronze_bucket            = "yt-data-pipeline-bronze-<your-suffix>"
s3_silver_bucket            = "yt-data-pipeline-silver-<your-suffix>"
s3_gold_bucket              = "yt-data-pipeline-gold-<your-suffix>"
athena_query_results_bucket = "yt-data-pipeline-athena-results-<your-suffix>"
glue_scripts_bucket         = "yt-data-pipeline-glue-<your-suffix>"

# Comma-separated YouTube region codes to ingest
regions = "US,FR,JP,MX"

glue_job_name_bronze_to_silver = "yt-bronze-to-silver-job"
glue_job_name_silver_to_gold   = "yt-silver-to-gold-job"

# RFC3339 UTC timestamp — first pipeline run (e.g. 7 PM Mexico City = 01:00 UTC next day)
pipeline_schedule_start_date = "2026-05-30T01:00:00Z"

lambda_function_name_json_to_parquet       = "yt-json-to-parquet"
lambda_function_name_youtube_api_ingestion = "yt-api-ingestion"
lambda_function_name_data_quality_checks   = "yt-quality-check"

youtube_api_key = "<your-youtube-api-key>"

# Find the right ARN for your region at https://aws-sdk-pandas.readthedocs.io/en/stable/layers.html
aws_wrangler_layer_arn = "arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python311:31"

notification_email = "your-email@example.com"
```

### 3. Deploy infrastructure

```bash
cd infrastructure
terraform init
terraform plan
terraform apply
```

This provisions all AWS resources: S3 buckets, Lambda functions, Glue jobs and crawlers, Athena workgroup, Step Functions state machine, and EventBridge Scheduler.

To tear down everything:

```bash
terraform destroy
```

### 4. Run Glue crawlers

After uploading, run both crawlers to populate the Glue Data Catalog:

```bash
aws glue start-crawler --name yt-data-pipeline-reference-data-crawler
aws glue start-crawler --name yt-data-pipeline-raw-statistics-crawler
```

Once complete, the tables will appear in Athena under the `yt-data-pipeline-db` database using the `yt-data-pipeline-workgroup` workgroup.

> **Note:** When running the ingestion Lambda for the first time, it automatically detects if the `raw_statistics` table is missing and triggers the crawler — no manual intervention needed for live data.

### 5. Run the bronze → silver Glue job

```bash
aws glue start-job-run --job-name yt-bronze-to-silver-job
```

Reads CSV files from the bronze bucket, casts types, cleans data, deduplicates, and writes Parquet to the silver bucket partitioned by region. The `silver_statistics` table is created/updated in the Glue catalog automatically.

```bash
# Check job status
aws glue get-job-runs --job-name yt-bronze-to-silver-job \
  --query 'JobRuns[0].{Status:JobRunState, Error:ErrorMessage}'
```

Logs are in CloudWatch under `/aws-glue/jobs/yt-bronze-to-silver-job` → `-driver` stream.

### 6. Run the silver → gold Glue job

```bash
aws glue start-job-run --job-name yt-silver-to-gold-job
```

Joins `silver_statistics` with `silver_reference_data` to enrich videos with category names, then builds three gold aggregation tables:

| Table | Description |
|---|---|
| `gold_trending_analytics` | Daily view/engagement totals per region |
| `gold_channel_analytics` | Per-channel reach, ranking, trending history |
| `gold_category_analytics` | Category share of views per region per day |

```bash
aws glue get-job-runs --job-name yt-silver-to-gold-job \
  --query 'JobRuns[0].{Status:JobRunState, Error:ErrorMessage}'
```

## Pipeline orchestration

The full pipeline is orchestrated by an AWS Step Functions state machine (`yt-data-pipeline-pipeline`) triggered automatically every 8 hours by EventBridge Scheduler starting from `pipeline_schedule_start_date`.

**Execution flow:**

1. **IngestFromYouTubeAPI** — Lambda fetches trending videos (CSV) and category data (JSON) for all configured `regions`
2. **WaitForS3Consistency** — 10-second wait for S3 eventual consistency
3. **ProcessInParallel** — two branches run concurrently:
   - `TransformReferenceData` — Lambda converts category JSON → Parquet in silver
   - `RunBronzeToSilverGlueJob` — ETL cleans and transforms trending CSVs to silver
4. **RunDataQualityChecks** — Lambda runs 9 checks (row count, nulls, schema, value ranges, freshness) via Athena
5. **EvaluateDataQuality** — if all checks pass, continue; otherwise send SNS alert and stop
6. **RunSilverToGoldGlueJob** — build the three gold aggregation tables
7. **NotifySuccess** — SNS notification with execution ID

To trigger a manual run:

```bash
aws stepfunctions start-execution \
  --state-machine-arn $(aws stepfunctions list-state-machines \
    --query "stateMachines[?name=='yt-data-pipeline-pipeline'].stateMachineArn" \
    --output text)
```

## Local development

A Jupyter notebook mirroring the bronze → silver Glue job is at `notebooks/bronze_to_silver.ipynb`. It runs the same PySpark/Glue SDK code via the official AWS Glue Docker image:

```bash
docker run -it \
  -v ~/.aws:/root/.aws \
  -v "$(pwd)":/home/glue_user/workspace \
  -p 8888:8888 \
  -e DISABLE_SSL=true \
  -e AWS_PROFILE=your-username \
  amazon/aws-glue-libs:glue_libs_4.0.0_image_01 \
  /home/glue_user/jupyter/jupyter_start.sh
```

Open `http://localhost:8888` and navigate to `notebooks/bronze_to_silver.ipynb`.
