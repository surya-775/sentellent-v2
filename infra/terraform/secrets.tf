resource "aws_secretsmanager_secret" "backend_secrets" {
  name = "${var.project_name}/backend-secrets"
}

resource "aws_secretsmanager_secret_version" "backend_secrets" {
  secret_id     = aws_secretsmanager_secret.backend_secrets.id
  secret_string = jsonencode({
    DATABASE_URL         = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.main.endpoint}/${var.db_name}"
    JWT_SECRET           = var.jwt_secret
    GEMINI_API_KEY       = var.gemini_api_key
    GOOGLE_CLIENT_ID     = var.google_client_id
    GOOGLE_CLIENT_SECRET = var.google_client_secret
  })
}
