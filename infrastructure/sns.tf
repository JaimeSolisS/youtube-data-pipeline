resource "aws_sns_topic" "pipeline_notifications" {
  name = "${var.project_name}-notifications"
}

# AWS sends a confirmation email on first apply — the subscription is inactive until confirmed
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.pipeline_notifications.arn
  protocol  = "email"
  endpoint  = var.notification_email
}