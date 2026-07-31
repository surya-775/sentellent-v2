resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id
  tags       = { Name = "${var.project_name}-db-subnet-group" }
}

# RDS Postgres 16 supports the pgvector extension (CREATE EXTENSION vector),
# which the app's initial Alembic migration enables on first deploy.
resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = "16.4"

  instance_class    = var.db_instance_class
  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = 7
  skip_final_snapshot     = false
  final_snapshot_identifier = "${var.project_name}-db-final-snapshot"
  deletion_protection     = false # set true once this is a real production system

  publicly_accessible = false
  multi_az             = false # bump to true for prod HA if budget allows

  tags = { Name = "${var.project_name}-db" }
}
