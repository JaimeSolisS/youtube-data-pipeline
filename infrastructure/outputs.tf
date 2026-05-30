# ── S3 ───────────────────────────────────────────────────────────────────────

output "s3_bronze_bucket" {
  value = aws_s3_bucket.bronze.bucket
}

output "s3_silver_bucket" {
  value = aws_s3_bucket.silver.bucket
}

output "s3_gold_bucket" {
  value = aws_s3_bucket.gold.bucket
}

output "s3_athena_query_results_bucket" {
  value = aws_s3_bucket.athena_query_results.bucket
}

output "s3_glue_scripts_bucket" {
  value = aws_s3_bucket.glue_scripts.bucket
}

# ── Lambda ────────────────────────────────────────────────────────────────────

output "lambda_youtube_api_ingestion" {
  value = aws_lambda_function.youtube_api_ingestion.function_name
}

output "lambda_json_to_parquet" {
  value = aws_lambda_function.json_to_parquet.function_name
}

output "lambda_data_quality_checks" {
  value = aws_lambda_function.data_quality_checks.function_name
}

# ── Glue ──────────────────────────────────────────────────────────────────────

output "glue_database_name" {
  value = aws_glue_catalog_database.main.name
}

output "glue_crawler_raw_statistics" {
  value = aws_glue_crawler.raw_statistics.name
}

output "glue_crawler_reference_data" {
  value = aws_glue_crawler.reference_data.name
}

output "glue_job_bronze_to_silver" {
  value = aws_glue_job.bronze_to_silver_script.name
}

output "glue_job_silver_to_gold" {
  value = aws_glue_job.silver_to_gold.name
}

# ── Athena ────────────────────────────────────────────────────────────────────

output "athena_workgroup" {
  value = aws_athena_workgroup.main.name
}

# ── Step Functions ────────────────────────────────────────────────────────────

output "state_machine_arn" {
  value = aws_sfn_state_machine.pipeline.arn
}

output "state_machine_name" {
  value = aws_sfn_state_machine.pipeline.name
}

# ── EventBridge ───────────────────────────────────────────────────────────────

output "pipeline_schedule_name" {
  value = aws_scheduler_schedule.pipeline.name
}

# ── SNS ───────────────────────────────────────────────────────────────────────

output "pipeline_notifications_topic" {
  value = aws_sns_topic.pipeline_notifications.arn
}
