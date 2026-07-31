variable "aws_region" {
  description = "AWS region — ap-south-1 (Mumbai) for lowest latency to Indian data sources/users"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  type    = string
  default = "sentellent-stock-analyst"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "db_username" {
  type      = string
  default   = "postgres"
  sensitive = true
}

variable "db_password" {
  description = "RDS master password — pass via TF_VAR_db_password or CI secret, never commit"
  type        = string
  sensitive   = true
}

variable "db_name" {
  type    = string
  default = "stockanalyst"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "jwt_secret" {
  description = "JWT signing secret — pass via TF_VAR_jwt_secret or CI secret"
  type        = string
  sensitive   = true
}

variable "gemini_api_key" {
  description = "Google Gemini API key (google-genai) — used for chat, tagging, persona extraction, and embeddings"
  type        = string
  sensitive   = true
  default     = ""
}

variable "google_client_id" {
  type    = string
  default = ""
}

variable "google_client_secret" {
  type      = string
  sensitive = true
  default   = ""
}

variable "backend_image_tag" {
  description = "Docker image tag for the backend, set by CI/CD on each deploy"
  type        = string
  default     = "latest"
}

variable "frontend_domain" {
  description = "Optional custom domain for CloudFront; leave blank to use the default CloudFront domain"
  type        = string
  default     = ""
}

variable "backend_cpu" {
  type    = number
  default = 512
}

variable "backend_memory" {
  type    = number
  default = 1024
}

variable "backend_desired_count" {
  type    = number
  default = 1
}
