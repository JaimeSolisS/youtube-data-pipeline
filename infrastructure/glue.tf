resource "aws_glue_catalog_database" "main" {
  name = "${var.project_name}-db"
}

# Crawls the JSON reference data (category files) in the bronze bucket
resource "aws_glue_crawler" "reference_data" {
  name          = "${var.project_name}-reference-data-crawler"
  database_name = aws_glue_catalog_database.main.name
  role          = aws_iam_role.glue_exec.arn

  s3_target {
    path = "s3://${var.s3_bronze_bucket}/youtube/raw_statistics_reference_data/"
  }
}

# Crawls the video statistics CSVs in the bronze bucket
resource "aws_glue_crawler" "raw_statistics" {
  name          = "${var.project_name}-raw-statistics-crawler"
  database_name = aws_glue_catalog_database.main.name
  role          = aws_iam_role.glue_exec.arn

  s3_target {
    path = "s3://${var.s3_bronze_bucket}/youtube/raw_statistics/"
  }
}

# Uploads the ETL script to S3 so Glue can reference it
resource "aws_s3_object" "bronze_to_silver_script" {
  bucket     = var.glue_scripts_bucket
  key        = "glue-scripts/bronze-to-silver.py"
  source     = "${path.module}/glue_jobs/bronze_to_silver.py"
  etag       = filemd5("${path.module}/glue_jobs/bronze_to_silver.py")
  depends_on = [aws_s3_bucket.glue_scripts]
}

resource "aws_s3_object" "silver_to_gold_script" {
  bucket     = var.glue_scripts_bucket
  key        = "glue-scripts/silver-to-gold.py"
  source     = "${path.module}/glue_jobs/silver_to_gold.py"
  etag       = filemd5("${path.module}/glue_jobs/silver_to_gold.py")
  depends_on = [aws_s3_bucket.glue_scripts]
}

resource "aws_glue_job" "silver_to_gold" {
  name     = var.glue_job_name_silver_to_gold
  role_arn = aws_iam_role.glue_exec.arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.glue_scripts_bucket}/glue-scripts/silver-to-gold.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--silver_database"                  = aws_glue_catalog_database.main.name
    "--silver_statistics_table"          = "silver_statistics"
    "--silver_reference_table"           = "silver_reference_data"
    "--gold_bucket"                      = var.s3_gold_bucket
    "--gold_database"                    = aws_glue_catalog_database.main.name
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-metrics"                   = "true"
    "--continuous-log-logGroup"          = "/aws-glue/jobs/${var.glue_job_name_silver_to_gold}"
  }

  glue_version      = "4.0"
  number_of_workers = 2
  worker_type       = "G.1X"
}

resource "aws_glue_job" "bronze_to_silver_script" {
  name     = var.glue_job_name_bronze_to_silver
  role_arn = aws_iam_role.glue_exec.arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.glue_scripts_bucket}/glue-scripts/bronze-to-silver.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                        = "python"
    "--bronze_bucket"                       = var.s3_bronze_bucket
    "--bronze_database"                     = aws_glue_catalog_database.main.name
    "--bronze_table"                        = "raw_statistics"
    "--silver_bucket"                       = var.s3_silver_bucket
    "--silver_database"                     = aws_glue_catalog_database.main.name
    "--silver_table"                        = "silver_statistics"
    "--enable-continuous-cloudwatch-log"    = "true"
    "--enable-metrics"                      = "true"
    "--continuous-log-logGroup"             = "/aws-glue/jobs/${var.glue_job_name_bronze_to_silver}"
  }

  glue_version      = "4.0"
  number_of_workers = 2
  worker_type       = "G.1X"
}