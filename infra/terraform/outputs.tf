output "backend_url" {
  description = "ALB DNS name — the backend API base URL"
  value       = "http://${aws_lb.main.dns_name}"
}

output "frontend_url" {
  description = "CloudFront distribution domain — the live frontend URL"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "rds_endpoint" {
  value     = aws_db_instance.main.endpoint
  sensitive = true
}

output "frontend_s3_bucket" {
  value = aws_s3_bucket.frontend.bucket
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.frontend.id
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.backend.name
}
