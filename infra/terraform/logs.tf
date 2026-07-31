resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project_name}-backend"
  retention_in_days = 14
}
