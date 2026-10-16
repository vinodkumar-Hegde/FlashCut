# ============================================================
# Controlled deployment/migration resources
# ============================================================

resource "aws_cloudwatch_log_group" "migration" {
  name = "/ecs/${local.name}/migration"

  retention_in_days = 30
}


resource "aws_ecs_task_definition" "migration" {
  family = "${local.name}-migration"

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = "256"
  memory = "512"

  execution_role_arn = (
    aws_iam_role.ecs_execution.arn
  )

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name = "migration"

      image = (
        "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
      )

      essential = true

      environment = local.common_environment

      secrets = local.common_secrets

      command = [
        "alembic",
        "-c",
        "/app/alembic.ini",
        "upgrade",
        "head",
      ]

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group = (
            aws_cloudwatch_log_group
            .migration
            .name
          )

          awslogs-region = (
            var.aws_region
          )

          awslogs-stream-prefix = "migration"
        }
      }
    }
  ])

  depends_on = [
    aws_secretsmanager_secret_version.database_url,
    aws_secretsmanager_secret_version.redis_url,
  ]
}


output "migration_task_definition_arn" {
  value = (
    aws_ecs_task_definition.migration.arn
  )
}


output "bootstrap_mode" {
  value = var.bootstrap_mode
}
