output "s3_bronze_bucket" {
  value = aws_s3_bucket.bronze.bucket
}

output "s3_silver_bucket" {
  value = aws_s3_bucket.silver.bucket
}

output "s3_gold_bucket" {
  value = aws_s3_bucket.gold.bucket
}

output "json_to_parquet_lambda" {
  value = aws_lambda_function.json_to_parquet.function_name
}

output "pipeline_notifications_topic" {
  value = aws_sns_topic.pipeline_notifications.name
}