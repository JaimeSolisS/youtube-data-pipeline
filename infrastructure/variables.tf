variable "project_name" {
  description = "Project name used as a prefix for shared resources"
  type        = string
}

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "s3_bronze_bucket" {
  description = "S3 bucket for raw ingested data (bronze layer)"
  type        = string
}

variable "s3_silver_bucket" {
  description = "S3 bucket for cleaned/transformed data (silver layer)"
  type        = string
}

variable "s3_gold_bucket" {
  description = "S3 bucket for aggregated/analytics-ready data (gold layer)"
  type        = string
}

variable "athena_query_results_bucket" {
  description = "S3 bucket for Athena query results"
  type        = string
}

variable "glue_scripts_bucket" {
  description = "S3 bucket for Glue scripts"
  type        = string
}

variable "glue_job_name_bronze_to_silver" {
  description = "Name of the Glue ETL job for video statistics"
  type        = string
}

variable "glue_job_name_silver_to_gold" {
  description = "Name of the Glue ETL job that builds gold aggregation tables"
  type        = string
}

variable "lambda_function_name_json_to_parquet" {
  description = "Name of the json-to-parquet Lambda function"
  type        = string
}

variable "lambda_function_name_youtube_api_ingestion" {
  description = "Name of the YouTube API ingestion Lambda function"
  type        = string
}

variable "lambda_function_name_data_quality_checks" {
  description = "Name of the data quality checks Lambda function"
  type        = string
}

variable "youtube_api_key" {
  description = "API key for accessing the YouTube Data API"
  type        = string
  sensitive   = true
}

variable "aws_wrangler_layer_arn" {
  description = "ARN of the AWS SDK for Pandas (awswrangler) Lambda layer."
  type        = string
}

variable "notification_email" {
  description = "Email address to receive pipeline notifications via SNS"
  type        = string
}
