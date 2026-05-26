# Zips the Lambda source folder for deployment
data "archive_file" "json_to_parquet" {
  type        = "zip"
  source_dir  = "${path.module}/lambdas/json_to_parquet"
  output_path = "${path.module}/lambdas/zips/json_to_parquet.zip"
}

# Lambda function — awswrangler and pandas are provided via the managed layer
resource "aws_lambda_function" "json_to_parquet" {
  function_name    = var.lambda_function_name_json_to_parquet
  role             = aws_iam_role.lambda_exec.arn  # shared role defined in iam.tf
  runtime          = "python3.11"
  handler          = "lambda.lambda_handler"
  timeout          = 300
  memory_size      = 512
  filename         = data.archive_file.json_to_parquet.output_path
  source_code_hash = data.archive_file.json_to_parquet.output_base64sha256

  layers = [var.aws_wrangler_layer_arn]

  environment {
    variables = {
      S3_BUCKET_SILVER = var.s3_silver_bucket
      SNS_ALERT_TOPIC_ARN = aws_sns_topic.pipeline_notifications.arn
      GLUE_DB = aws_glue_catalog_database.main.name
      GLUE_SILVER_TABLE =  "silver_reference_data"
    }
  }
}

# Allows S3 to invoke the Lambda (required in addition to the bucket notification)
resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.json_to_parquet.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.bronze.arn
}

# Fires the Lambda whenever a .json file is created under the reference data prefix
resource "aws_s3_bucket_notification" "bronze_trigger" {
  bucket = aws_s3_bucket.bronze.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.json_to_parquet.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "youtube/raw_statistics_reference_data/"
    filter_suffix       = ".json"
  }

  depends_on = [aws_lambda_permission.allow_s3]
}
