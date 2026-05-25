resource "aws_s3_bucket" "bronze" {
  bucket = var.s3_bronze_bucket
}

resource "aws_s3_bucket" "silver" {
  bucket = var.s3_silver_bucket
}
resource "aws_s3_bucket" "gold" {
  bucket = var.s3_gold_bucket
}
