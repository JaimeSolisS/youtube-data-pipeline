# YouTube Data Pipeline

## Prerequisites

- `curl`
- `unzip`
- `make`
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.3.0
- AWS account with an IAM user that has programmatic access

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

Credentials are stored in `~/.aws/credentials`

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
aws_region       = "us-east-1"

s3_bronze_bucket = "yt-data-pipeline-bronze-<your-suffix>"
s3_silver_bucket = "yt-data-pipeline-silver-<your-suffix>"
s3_gold_bucket   = "yt-data-pipeline-gold-<your-suffix>"
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
