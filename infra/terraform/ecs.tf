resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  idle_timeout       = 90 # headroom for chat requests chaining several sequential Gemini calls

  tags = { Name = "${var.project_name}-alb" }
}

resource "aws_lb_target_group" "backend" {
  name        = "${var.project_name}-backend-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 15
    matcher             = "200"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name         = "backend"
      image        = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
      essential    = true
      portMappings = [{
        containerPort = 8000
        protocol      = "tcp"
      }]
      environment = [
        { name = "ENV", value = var.environment },
        { name = "FRONTEND_URL", value = var.frontend_domain != "" ? "https://${var.frontend_domain}" : "https://${aws_cloudfront_distribution.frontend.domain_name}" },
        { name = "OAUTH_REDIRECT_URI", value = var.frontend_domain != "" ? "https://${var.frontend_domain}/api/auth/google/callback" : "https://${aws_cloudfront_distribution.frontend.domain_name}/api/auth/google/callback" },
        { name = "CHAT_MODEL", value = "gemini-flash-latest" },
        { name = "EMBEDDING_MODEL", value = "gemini-embedding-001" },
        { name = "EMBEDDING_DIM", value = "768" },
      ]
      secrets = [
        { name = "DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.backend_secrets.arn}:DATABASE_URL::" },
        { name = "JWT_SECRET", valueFrom = "${aws_secretsmanager_secret.backend_secrets.arn}:JWT_SECRET::" },
        { name = "GEMINI_API_KEY", valueFrom = "${aws_secretsmanager_secret.backend_secrets.arn}:GEMINI_API_KEY::" },
        { name = "GOOGLE_CLIENT_ID", valueFrom = "${aws_secretsmanager_secret.backend_secrets.arn}:GOOGLE_CLIENT_ID::" },
        { name = "GOOGLE_CLIENT_SECRET", valueFrom = "${aws_secretsmanager_secret.backend_secrets.arn}:GOOGLE_CLIENT_SECRET::" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options   = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "backend"
        }
      }
    }
  ])

  tags = { Name = "${var.project_name}-backend-task" }
}

resource "aws_ecs_service" "backend" {
  name            = "${var.project_name}-backend-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_backend.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  depends_on = [aws_lb_listener.http]

  lifecycle {
    ignore_changes = [task_definition] # allow CI/CD to update the task def without tf drift fights
  }

  tags = { Name = "${var.project_name}-backend-service" }
}
