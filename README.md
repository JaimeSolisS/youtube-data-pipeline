# YouTube Data Pipeline

## Prerequisites

- `curl`
- `unzip`
- `make`
- `python` with `boto3` (`pip install boto3`)
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.3.0
- AWS account with an IAM user that has programmatic access
- YouTube Data API v3 key — create one at [console.cloud.google.com](https://console.cloud.google.com) under APIs & Services → Credentials. Add it to `infrastructure/terraform.tfvars` (see step 3):

### Configure AWS credentials

**Option A — default profile**

```bash
aws configure
```

You will be prompted for your Access Key ID, Secret Access Key, and default region.

**Option B — named profile**

```bash
aws configure --profile your-username
```

Then export the profile before running Terraform:

```bash
export AWS_PROFILE=your-username
```

Credentials are stored in `~/.aws/credentials` and config in `~/.aws/config`.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/JaimeSolisS/youtube-data-pipeline.git
cd youtube-data-pipeline
```

### 2. Download the dataset

```bash
make download-kaggle
```

This will download and extract the dataset into a `data/` folder. The dataset includes trending video CSVs and category JSON files for 10 countries: CA, DE, FR, GB, IN, JP, KR, MX, RU, US.

### 3. Configure Terraform

Copy the example file and fill in your values:

```bash
cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars
```

Edit `infrastructure/terraform.tfvars` — S3 bucket names must be globally unique, so add a personal suffix:

```hcl
project_name        = "yt-data-pipeline"
aws_region          = "us-east-1"

s3_bronze_bucket              = "yt-data-pipeline-bronze-<your-suffix>"
s3_silver_bucket              = "yt-data-pipeline-silver-<your-suffix>"
s3_gold_bucket                = "yt-data-pipeline-gold-<your-suffix>"
athena_query_results_bucket   = "yt-data-pipeline-athena-results-<your-suffix>"

lambda_function_name_json_to_parquet = "yt-json-to-parquet"
lambda_function_name_youtube_api_ingestion = "yt-api-ingestion"
youtube_api_key                            = "<your-youtube-api-key>"
# Find the right ARN for your region at https://aws-sdk-pandas.readthedocs.io/en/stable/layers.html
aws_wrangler_layer_arn = "arn:aws:lambda:us-east-1:<your-account>:layer:AWSSDKPandas-Python311:31"

notification_email = "your-email@example.com"
```

### 4. Deploy infrastructure

```bash
cd infrastructure
terraform init
terraform plan
terraform apply
```

To tear down all resources:

```bash
terraform destroy
```

### 5. Upload data to S3

```bash
make upload-to-s3 bucket=yt-data-pipeline-bronze-<your-suffix>
```

This uploads all CSV and JSON files from the `data/` folder to the bronze S3 bucket, partitioned by region.

### 6. Run Glue crawlers

After uploading, run both crawlers to populate the Glue Data Catalog:

```bash
aws glue start-crawler --name yt-data-pipeline-reference-data-crawler
aws glue start-crawler --name yt-data-pipeline-raw-statistics-crawler
```

Once complete, the tables will be available in Athena under the `yt-data-pipeline-db` database using the `yt-data-pipeline-workgroup` workgroup.
