resource "aws_s3_bucket" "bronze" {
  bucket = var.s3_bronze_bucket
}

resource "aws_s3_bucket_lifecycle_configuration" "bronzeGlacier" {
  bucket = aws_s3_bucket.bronze.bucket
  rule {
    id     = "move-old-objects-to-glacier"
    status = "Enabled"
    filter {}
    transition {
      days          = 365
      storage_class = "GLACIER"
    }
  }
}

resource "aws_s3_bucket" "silver" {
  bucket = var.s3_silver_bucket
}
resource "aws_s3_bucket" "gold" {
  bucket = var.s3_gold_bucket
}

resource "aws_s3_bucket" "athena_query_results" {
  bucket = var.athena_query_results_bucket
}

resource "aws_s3_bucket" "glue_scripts" {
  bucket = var.glue_scripts_bucket
}