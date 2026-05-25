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

variable "lambda_function_name_json_to_parquet" {
  description = "Name of the json-to-parquet Lambda function"
  type        = string
}

variable "aws_wrangler_layer_arn" {
  description = "ARN of the AWS SDK for Pandas (awswrangler) Lambda layer."
  type        = string
}
