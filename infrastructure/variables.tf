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
