# ── IAM: Step Functions execution role ───────────────────────────────────────

resource "aws_iam_role" "sfn_exec" {
  name = "${var.project_name}-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "sfn_exec" {
  name = "${var.project_name}-sfn-policy"
  role = aws_iam_role.sfn_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = [
          aws_lambda_function.youtube_api_ingestion.arn,
          aws_lambda_function.json_to_parquet.arn,
          aws_lambda_function.data_quality_checks.arn,
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "glue:StartJobRun",
          "glue:GetJobRun",
          "glue:GetJobRuns",
          "glue:BatchStopJobRun",
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.pipeline_notifications.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups",
        ]
        Resource = "*"
      },
    ]
  })
}


# ── State Machine ─────────────────────────────────────────────────────────────

resource "aws_sfn_state_machine" "pipeline" {
  name     = "${var.project_name}-pipeline"
  role_arn = aws_iam_role.sfn_exec.arn

  definition = templatefile("${path.module}/step_functions/pipeline.json.tftpl", {
    youtube_api_lambda_arn    = aws_lambda_function.youtube_api_ingestion.arn
    json_to_parquet_lambda_arn = aws_lambda_function.json_to_parquet.arn
    dq_lambda_arn             = aws_lambda_function.data_quality_checks.arn
    bronze_to_silver_job_name = var.glue_job_name_bronze_to_silver
    silver_to_gold_job_name   = var.glue_job_name_silver_to_gold
    sns_topic_arn             = aws_sns_topic.pipeline_notifications.arn
    glue_database             = aws_glue_catalog_database.main.name
    bronze_bucket             = var.s3_bronze_bucket
    silver_bucket             = var.s3_silver_bucket
    gold_bucket               = var.s3_gold_bucket
    exec_id_ref               = "$$.Execution.Id"
  })
}


# ── IAM: EventBridge → Step Functions ────────────────────────────────────────

resource "aws_iam_role" "eventbridge_sfn" {
  name = "${var.project_name}-eventbridge-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_sfn" {
  name = "${var.project_name}-eventbridge-sfn-policy"
  role = aws_iam_role.eventbridge_sfn.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["states:StartExecution"]
      Resource = aws_sfn_state_machine.pipeline.arn
    }]
  })
}


# ── EventBridge Scheduler: every 8 hours ─────────────────────────────────────

resource "aws_scheduler_schedule" "pipeline" {
  name       = "${var.project_name}-pipeline-schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "rate(8 hours)"
  start_date          = var.pipeline_schedule_start_date

  target {
    arn      = aws_sfn_state_machine.pipeline.arn
    role_arn = aws_iam_role.eventbridge_sfn.arn

    input = jsonencode({
      triggered_by = "eventbridge_scheduler"
    })
  }
}


# ── Outputs ───────────────────────────────────────────────────────────────────

output "state_machine_arn" {
  value = aws_sfn_state_machine.pipeline.arn
}

output "pipeline_schedule" {
  value = "Every 8 hours via EventBridge Scheduler: ${aws_scheduler_schedule.pipeline.name}"
}
