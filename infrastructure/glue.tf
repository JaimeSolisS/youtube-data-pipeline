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