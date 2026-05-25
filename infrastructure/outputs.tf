output "s3_bronze_bucket" {
  value = aws_s3_bucket.bronze.bucket
}

output "s3_silver_bucket" {
  value = aws_s3_bucket.silver.bucket
}

output "s3_gold_bucket" {
  value = aws_s3_bucket.gold.bucket
}
