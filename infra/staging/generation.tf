# ============================================================
# DT-FlashCut independent generation pipelines
#
# Quick Summary:
#   API -> transactional outbox -> dispatcher -> SQS -> worker
#
# Learning Materials:
#   API -> transactional outbox -> dispatcher -> SQS -> worker
#
# Existing summary/notes services remain unchanged.
# ============================================================


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

variable "generation_log_retention_days" {
  type    = number
  default = 30
}

variable "generation_visibility_timeout_seconds" {
  type    = number
  default = 300
}

variable "generation_scale_out_queue_depth" {
  type    = number
  default = 5
}

variable "generation_oldest_message_alarm_seconds" {
  type    = number
  default = 300
}

variable "quick_summary_worker_min_count" {
  type    = number
  default = 1
}

variable "quick_summary_worker_max_count" {
  type    = number
  default = 10

  validation {
    condition = (
      var.quick_summary_worker_max_count
      >= var.quick_summary_worker_min_count
    )

    error_message = "quick_summary_worker_max_count must be greater than or equal to the minimum."
  }
}

variable "learning_material_worker_min_count" {
  type    = number
  default = 1
}

variable "learning_material_worker_max_count" {
  type    = number
  default = 10

  validation {
    condition = (
      var.learning_material_worker_max_count
      >= var.learning_material_worker_min_count
    )

    error_message = "learning_material_worker_max_count must be greater than or equal to the minimum."
  }
}

variable "generation_alarm_actions" {
  type    = list(string)
  default = []
}


# ------------------------------------------------------------
# Quick Summary SQS + DLQ
# ------------------------------------------------------------

resource "aws_sqs_queue" "quick_summary_dlq" {
  name = "${local.name}-quick-summary-dlq"

  message_retention_seconds = 1209600

  sqs_managed_sse_enabled = true
}


resource "aws_sqs_queue" "quick_summary" {
  name = "${local.name}-quick-summary"

  visibility_timeout_seconds = (
    var.generation_visibility_timeout_seconds
  )

  receive_wait_time_seconds = 20

  message_retention_seconds = 345600

  sqs_managed_sse_enabled = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = (
      aws_sqs_queue.quick_summary_dlq.arn
    )

    maxReceiveCount = 5
  })
}


# ------------------------------------------------------------
# Learning Materials SQS + DLQ
# ------------------------------------------------------------

resource "aws_sqs_queue" "learning_material" {
  name = "${local.name}-learning-material"

  visibility_timeout_seconds = (
    var.generation_visibility_timeout_seconds
  )

  receive_wait_time_seconds = 20

  message_retention_seconds = 345600

  sqs_managed_sse_enabled = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = (
      aws_sqs_queue.learning_material_dlq.arn
    )

    maxReceiveCount = 5
  })
}


resource "aws_sqs_queue" "learning_material_dlq" {
  name = "${local.name}-learning-material-dlq"

  message_retention_seconds = 1209600

  sqs_managed_sse_enabled = true
}


# ------------------------------------------------------------
# CloudWatch logs
# ------------------------------------------------------------

resource "aws_cloudwatch_log_group" "generation_dispatcher" {
  name = (
    "/ecs/${local.name}/generation-dispatcher"
  )

  retention_in_days = (
    var.generation_log_retention_days
  )
}


resource "aws_cloudwatch_log_group" "quick_summary" {
  name = (
    "/ecs/${local.name}/quick-summary"
  )

  retention_in_days = (
    var.generation_log_retention_days
  )
}


resource "aws_cloudwatch_log_group" "learning_material" {
  name = (
    "/ecs/${local.name}/learning-material"
  )

  retention_in_days = (
    var.generation_log_retention_days
  )
}


# ------------------------------------------------------------
# Dedicated task roles
#
# The shared ECS execution role is retained only for:
#   - ECR image pull
#   - CloudWatch log setup
#   - Secrets Manager secret injection
#
# Runtime AWS permissions are separated below.
# ------------------------------------------------------------

data "aws_iam_policy_document" "generation_task_assume" {
  statement {
    effect = "Allow"

    actions = [
      "sts:AssumeRole",
    ]

    principals {
      type = "Service"

      identifiers = [
        "ecs-tasks.amazonaws.com",
      ]
    }
  }
}


resource "aws_iam_role" "generation_dispatcher_task" {
  name = (
    "${local.name}-generation-dispatcher-task"
  )

  assume_role_policy = (
    data.aws_iam_policy_document
    .generation_task_assume
    .json
  )
}


resource "aws_iam_role" "quick_summary_task" {
  name = (
    "${local.name}-quick-summary-task"
  )

  assume_role_policy = (
    data.aws_iam_policy_document
    .generation_task_assume
    .json
  )
}


resource "aws_iam_role" "learning_material_task" {
  name = (
    "${local.name}-learning-material-task"
  )

  assume_role_policy = (
    data.aws_iam_policy_document
    .generation_task_assume
    .json
  )
}


# ------------------------------------------------------------
# Dispatcher permissions
#
# Dispatcher only publishes to the two generation queues.
# ------------------------------------------------------------

resource "aws_iam_role_policy" "generation_dispatcher" {
  name = (
    "${local.name}-generation-dispatcher"
  )

  role = (
    aws_iam_role
    .generation_dispatcher_task
    .id
  )

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueAttributes",
        ]

        Resource = [
          aws_sqs_queue.quick_summary.arn,
          aws_sqs_queue.learning_material.arn,
        ]
      }
    ]
  })
}


# ------------------------------------------------------------
# Quick Summary worker permissions
#
# A worker may:
#   - consume only its own SQS queue
#   - check an already-started Transcribe job
#   - download the completed transcript JSON
#   - invoke Bedrock
#
# It cannot publish into the Learning Materials queue.
# ------------------------------------------------------------

resource "aws_iam_role_policy" "quick_summary_worker" {
  name = (
    "${local.name}-quick-summary-worker"
  )

  role = (
    aws_iam_role
    .quick_summary_task
    .id
  )

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:ChangeMessageVisibility",
          "sqs:GetQueueAttributes",
        ]

        Resource = [
          aws_sqs_queue.quick_summary.arn,
        ]
      },

      {
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
        ]

        Resource = [
          "${aws_s3_bucket.staging.arn}/transcripts/*",
        ]
      },

      {
        Effect = "Allow"

        Action = [
          "transcribe:GetTranscriptionJob",
        ]

        Resource = "*"
      },

      {
        Effect = "Allow"

        Action = [
          "bedrock:InvokeModel",
        ]

        Resource = "*"
      }
    ]
  })
}


# ------------------------------------------------------------
# Learning Materials worker permissions
# ------------------------------------------------------------

resource "aws_iam_role_policy" "learning_material_worker" {
  name = (
    "${local.name}-learning-material-worker"
  )

  role = (
    aws_iam_role
    .learning_material_task
    .id
  )

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:ChangeMessageVisibility",
          "sqs:GetQueueAttributes",
        ]

        Resource = [
          aws_sqs_queue.learning_material.arn,
        ]
      },

      {
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
        ]

        Resource = [
          "${aws_s3_bucket.staging.arn}/transcripts/*",
        ]
      },

      {
        Effect = "Allow"

        Action = [
          "transcribe:GetTranscriptionJob",
        ]

        Resource = "*"
      },

      {
        Effect = "Allow"

        Action = [
          "bedrock:InvokeModel",
        ]

        Resource = "*"
      }
    ]
  })
}


# ------------------------------------------------------------
# Generation dispatcher task
# ------------------------------------------------------------

resource "aws_ecs_task_definition" "generation_dispatcher" {
  family = (
    "${local.name}-generation-dispatcher"
  )

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = "256"
  memory = "512"

  execution_role_arn = (
    aws_iam_role.ecs_execution.arn
  )

  task_role_arn = (
    aws_iam_role
    .generation_dispatcher_task
    .arn
  )

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name = "generation-dispatcher"

      image = (
        "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
      )

      essential = true

      environment = concat(
        local.common_environment,
        [
          {
            name = "QUICK_SUMMARY_QUEUE_URL"

            value = (
              aws_sqs_queue
              .quick_summary
              .url
            )
          },

          {
            name = "LEARNING_MATERIAL_QUEUE_URL"

            value = (
              aws_sqs_queue
              .learning_material
              .url
            )
          },

          {
            name = "GENERATION_VISIBILITY_TIMEOUT_SECONDS"
            value = tostring(
              var.generation_visibility_timeout_seconds
            )
          },

          {
            name  = "GENERATION_HEARTBEAT_INTERVAL_SECONDS"
            value = "60"
          },

          {
            name  = "GENERATION_QUEUE_PUBLISH_MAX_ATTEMPTS"
            value = "20"
          },

          {
            name  = "GENERATION_DISPATCH_POLL_SECONDS"
            value = "0.5"
          },

          {
            name  = "GENERATION_OUTBOX_BATCH_SIZE"
            value = "20"
          },

          {
            name  = "GENERATION_STALE_AFTER_SECONDS"
            value = "180"
          },
        ]
      )

      secrets = local.common_secrets

      command = [
        "python",
        "-m",
        "app.workers.generation_outbox_dispatcher",
      ]

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group = (
            aws_cloudwatch_log_group
            .generation_dispatcher
            .name
          )

          awslogs-region = (
            var.aws_region
          )

          awslogs-stream-prefix = (
            "generation-dispatcher"
          )
        }
      }
    }
  ])
}


# ------------------------------------------------------------
# Quick Summary task
# ------------------------------------------------------------

resource "aws_ecs_task_definition" "quick_summary" {
  family = (
    "${local.name}-quick-summary"
  )

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = "256"
  memory = "512"

  execution_role_arn = (
    aws_iam_role.ecs_execution.arn
  )

  task_role_arn = (
    aws_iam_role
    .quick_summary_task
    .arn
  )

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name = "quick-summary"

      image = (
        "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
      )

      essential = true

      environment = concat(
        local.common_environment,
        [
          {
            name = "QUICK_SUMMARY_QUEUE_URL"

            value = (
              aws_sqs_queue
              .quick_summary
              .url
            )
          },

          {
            name = "LEARNING_MATERIAL_QUEUE_URL"

            value = (
              aws_sqs_queue
              .learning_material
              .url
            )
          },

          {
            name = "GENERATION_VISIBILITY_TIMEOUT_SECONDS"

            value = tostring(
              var.generation_visibility_timeout_seconds
            )
          },

          {
            name  = "GENERATION_HEARTBEAT_INTERVAL_SECONDS"
            value = "60"
          },

          {
            name  = "GENERATION_QUEUE_PUBLISH_MAX_ATTEMPTS"
            value = "20"
          },

          {
            name  = "GENERATION_DISPATCH_POLL_SECONDS"
            value = "0.5"
          },

          {
            name  = "GENERATION_OUTBOX_BATCH_SIZE"
            value = "20"
          },

          {
            name  = "GENERATION_STALE_AFTER_SECONDS"
            value = "180"
          },
        ]
      )

      secrets = local.common_secrets

      command = [
        "python",
        "-m",
        "app.workers.quick_summary_worker",
      ]

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group = (
            aws_cloudwatch_log_group
            .quick_summary
            .name
          )

          awslogs-region = (
            var.aws_region
          )

          awslogs-stream-prefix = (
            "quick-summary"
          )
        }
      }
    }
  ])
}


# ------------------------------------------------------------
# Learning Materials task
# ------------------------------------------------------------

resource "aws_ecs_task_definition" "learning_material" {
  family = (
    "${local.name}-learning-material"
  )

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = "512"
  memory = "1024"

  execution_role_arn = (
    aws_iam_role.ecs_execution.arn
  )

  task_role_arn = (
    aws_iam_role
    .learning_material_task
    .arn
  )

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name = "learning-material"

      image = (
        "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
      )

      essential = true

      environment = concat(
        local.common_environment,
        [
          {
            name = "QUICK_SUMMARY_QUEUE_URL"

            value = (
              aws_sqs_queue
              .quick_summary
              .url
            )
          },

          {
            name = "LEARNING_MATERIAL_QUEUE_URL"

            value = (
              aws_sqs_queue
              .learning_material
              .url
            )
          },

          {
            name = "GENERATION_VISIBILITY_TIMEOUT_SECONDS"

            value = tostring(
              var.generation_visibility_timeout_seconds
            )
          },

          {
            name  = "GENERATION_HEARTBEAT_INTERVAL_SECONDS"
            value = "60"
          },

          {
            name  = "GENERATION_QUEUE_PUBLISH_MAX_ATTEMPTS"
            value = "20"
          },

          {
            name  = "GENERATION_DISPATCH_POLL_SECONDS"
            value = "0.5"
          },

          {
            name  = "GENERATION_OUTBOX_BATCH_SIZE"
            value = "20"
          },

          {
            name  = "GENERATION_STALE_AFTER_SECONDS"
            value = "180"
          },
        ]
      )

      secrets = local.common_secrets

      command = [
        "python",
        "-m",
        "app.workers.learning_material_worker",
      ]

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group = (
            aws_cloudwatch_log_group
            .learning_material
            .name
          )

          awslogs-region = (
            var.aws_region
          )

          awslogs-stream-prefix = (
            "learning-material"
          )
        }
      }
    }
  ])
}


# ------------------------------------------------------------
# ECS services
# ------------------------------------------------------------

resource "aws_ecs_service" "generation_dispatcher" {
  name = (
    "${local.name}-generation-dispatcher"
  )

  cluster = (
    aws_ecs_cluster.main.id
  )

  task_definition = (
    aws_ecs_task_definition
    .generation_dispatcher
    .arn
  )

  desired_count = 1

  launch_type = "FARGATE"

  platform_version = "LATEST"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets = (
      aws_subnet.private[*].id
    )

    security_groups = [
      aws_security_group.tasks.id,
    ]

    assign_public_ip = false
  }
}


resource "aws_ecs_service" "quick_summary" {
  name = (
    "${local.name}-quick-summary"
  )

  cluster = (
    aws_ecs_cluster.main.id
  )

  task_definition = (
    aws_ecs_task_definition
    .quick_summary
    .arn
  )

  desired_count = (
    var.quick_summary_worker_min_count
  )

  launch_type = "FARGATE"

  platform_version = "LATEST"

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets = (
      aws_subnet.private[*].id
    )

    security_groups = [
      aws_security_group.tasks.id,
    ]

    assign_public_ip = false
  }

  lifecycle {
    ignore_changes = [
      desired_count,
    ]
  }
}


resource "aws_ecs_service" "learning_material" {
  name = (
    "${local.name}-learning-material"
  )

  cluster = (
    aws_ecs_cluster.main.id
  )

  task_definition = (
    aws_ecs_task_definition
    .learning_material
    .arn
  )

  desired_count = (
    var.learning_material_worker_min_count
  )

  launch_type = "FARGATE"

  platform_version = "LATEST"

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets = (
      aws_subnet.private[*].id
    )

    security_groups = [
      aws_security_group.tasks.id,
    ]

    assign_public_ip = false
  }

  lifecycle {
    ignore_changes = [
      desired_count,
    ]
  }
}


# ------------------------------------------------------------
# Application Auto Scaling targets
# ------------------------------------------------------------

resource "aws_appautoscaling_target" "quick_summary" {
  service_namespace = "ecs"

  resource_id = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.quick_summary.name}"

  scalable_dimension = (
    "ecs:service:DesiredCount"
  )

  min_capacity = (
    var.quick_summary_worker_min_count
  )

  max_capacity = (
    var.quick_summary_worker_max_count
  )
}


resource "aws_appautoscaling_target" "learning_material" {
  service_namespace = "ecs"

  resource_id = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.learning_material.name}"

  scalable_dimension = (
    "ecs:service:DesiredCount"
  )

  min_capacity = (
    var.learning_material_worker_min_count
  )

  max_capacity = (
    var.learning_material_worker_max_count
  )
}


# ------------------------------------------------------------
# Quick Summary scaling policies
# ------------------------------------------------------------

resource "aws_appautoscaling_policy" "quick_summary_scale_out" {
  name = (
    "${local.name}-quick-summary-scale-out"
  )

  policy_type = "StepScaling"

  service_namespace = (
    aws_appautoscaling_target
    .quick_summary
    .service_namespace
  )

  resource_id = (
    aws_appautoscaling_target
    .quick_summary
    .resource_id
  )

  scalable_dimension = (
    aws_appautoscaling_target
    .quick_summary
    .scalable_dimension
  )

  step_scaling_policy_configuration {
    adjustment_type = "ChangeInCapacity"

    cooldown = 60

    metric_aggregation_type = "Maximum"

    step_adjustment {
      metric_interval_lower_bound = 0

      scaling_adjustment = 1
    }
  }
}


resource "aws_appautoscaling_policy" "quick_summary_scale_in" {
  name = (
    "${local.name}-quick-summary-scale-in"
  )

  policy_type = "StepScaling"

  service_namespace = (
    aws_appautoscaling_target
    .quick_summary
    .service_namespace
  )

  resource_id = (
    aws_appautoscaling_target
    .quick_summary
    .resource_id
  )

  scalable_dimension = (
    aws_appautoscaling_target
    .quick_summary
    .scalable_dimension
  )

  step_scaling_policy_configuration {
    adjustment_type = "ChangeInCapacity"

    cooldown = 300

    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_upper_bound = 0

      scaling_adjustment = -1
    }
  }
}


# ------------------------------------------------------------
# Learning Materials scaling policies
# ------------------------------------------------------------

resource "aws_appautoscaling_policy" "learning_material_scale_out" {
  name = (
    "${local.name}-learning-material-scale-out"
  )

  policy_type = "StepScaling"

  service_namespace = (
    aws_appautoscaling_target
    .learning_material
    .service_namespace
  )

  resource_id = (
    aws_appautoscaling_target
    .learning_material
    .resource_id
  )

  scalable_dimension = (
    aws_appautoscaling_target
    .learning_material
    .scalable_dimension
  )

  step_scaling_policy_configuration {
    adjustment_type = "ChangeInCapacity"

    cooldown = 60

    metric_aggregation_type = "Maximum"

    step_adjustment {
      metric_interval_lower_bound = 0

      scaling_adjustment = 1
    }
  }
}


resource "aws_appautoscaling_policy" "learning_material_scale_in" {
  name = (
    "${local.name}-learning-material-scale-in"
  )

  policy_type = "StepScaling"

  service_namespace = (
    aws_appautoscaling_target
    .learning_material
    .service_namespace
  )

  resource_id = (
    aws_appautoscaling_target
    .learning_material
    .resource_id
  )

  scalable_dimension = (
    aws_appautoscaling_target
    .learning_material
    .scalable_dimension
  )

  step_scaling_policy_configuration {
    adjustment_type = "ChangeInCapacity"

    cooldown = 300

    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_upper_bound = 0

      scaling_adjustment = -1
    }
  }
}


# ------------------------------------------------------------
# Quick Summary queue-depth autoscaling alarms
# ------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "quick_summary_queue_high" {
  alarm_name = (
    "${local.name}-quick-summary-queue-high"
  )

  alarm_description = "Scale Quick Summary workers when the SQS backlog grows."

  namespace = "AWS/SQS"

  metric_name = (
    "ApproximateNumberOfMessagesVisible"
  )

  statistic = "Maximum"

  period = 60

  evaluation_periods = 2

  datapoints_to_alarm = 2

  comparison_operator = (
    "GreaterThanOrEqualToThreshold"
  )

  threshold = (
    var.generation_scale_out_queue_depth
  )

  dimensions = {
    QueueName = (
      aws_sqs_queue.quick_summary.name
    )
  }

  alarm_actions = concat(
    [
      aws_appautoscaling_policy
      .quick_summary_scale_out
      .arn,
    ],
    var.generation_alarm_actions,
  )

  treat_missing_data = "notBreaching"
}



resource "aws_cloudwatch_metric_alarm" "quick_summary_queue_empty" {
  alarm_name = "${local.name}-quick-summary-queue-empty"

  alarm_description = "Scale Quick Summary workers down only when no queued or in-flight work remains."

  comparison_operator = "LessThanOrEqualToThreshold"

  threshold = 0

  evaluation_periods = 5

  datapoints_to_alarm = 5

  alarm_actions = [
    aws_appautoscaling_policy.quick_summary_scale_in.arn,
  ]

  treat_missing_data = "breaching"

  metric_query {
    id          = "visible"
    return_data = false

    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesVisible"
      period      = 60
      stat        = "Average"

      dimensions = {
        QueueName = aws_sqs_queue.quick_summary.name
      }
    }
  }

  metric_query {
    id          = "inflight"
    return_data = false

    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesNotVisible"
      period      = 60
      stat        = "Average"

      dimensions = {
        QueueName = aws_sqs_queue.quick_summary.name
      }
    }
  }

  metric_query {
    id          = "backlog"
    expression  = "visible + inflight"
    label       = "Quick Summary total backlog"
    return_data = true
  }
}



# ------------------------------------------------------------
# Learning Materials queue-depth autoscaling alarms
# ------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "learning_material_queue_high" {
  alarm_name = (
    "${local.name}-learning-material-queue-high"
  )

  alarm_description = "Scale Learning Materials workers when the SQS backlog grows."

  namespace = "AWS/SQS"

  metric_name = (
    "ApproximateNumberOfMessagesVisible"
  )

  statistic = "Maximum"

  period = 60

  evaluation_periods = 2

  datapoints_to_alarm = 2

  comparison_operator = (
    "GreaterThanOrEqualToThreshold"
  )

  threshold = (
    var.generation_scale_out_queue_depth
  )

  dimensions = {
    QueueName = (
      aws_sqs_queue.learning_material.name
    )
  }

  alarm_actions = concat(
    [
      aws_appautoscaling_policy
      .learning_material_scale_out
      .arn,
    ],
    var.generation_alarm_actions,
  )

  treat_missing_data = "notBreaching"
}



resource "aws_cloudwatch_metric_alarm" "learning_material_queue_empty" {
  alarm_name = "${local.name}-learning-material-queue-empty"

  alarm_description = "Scale Learning Materials workers down only when no queued or in-flight work remains."

  comparison_operator = "LessThanOrEqualToThreshold"

  threshold = 0

  evaluation_periods = 5

  datapoints_to_alarm = 5

  alarm_actions = [
    aws_appautoscaling_policy.learning_material_scale_in.arn,
  ]

  treat_missing_data = "breaching"

  metric_query {
    id          = "visible"
    return_data = false

    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesVisible"
      period      = 60
      stat        = "Average"

      dimensions = {
        QueueName = aws_sqs_queue.learning_material.name
      }
    }
  }

  metric_query {
    id          = "inflight"
    return_data = false

    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesNotVisible"
      period      = 60
      stat        = "Average"

      dimensions = {
        QueueName = aws_sqs_queue.learning_material.name
      }
    }
  }

  metric_query {
    id          = "backlog"
    expression  = "visible + inflight"
    label       = "Learning Materials total backlog"
    return_data = true
  }
}



# ------------------------------------------------------------
# Queue-age alarms
# ------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "quick_summary_oldest_message" {
  alarm_name = (
    "${local.name}-quick-summary-oldest-message"
  )

  alarm_description = "Quick Summary queue has an old unprocessed message."

  namespace = "AWS/SQS"

  metric_name = (
    "ApproximateAgeOfOldestMessage"
  )

  statistic = "Maximum"

  period = 60

  evaluation_periods = 2

  datapoints_to_alarm = 2

  comparison_operator = (
    "GreaterThanOrEqualToThreshold"
  )

  threshold = (
    var.generation_oldest_message_alarm_seconds
  )

  dimensions = {
    QueueName = (
      aws_sqs_queue.quick_summary.name
    )
  }

  alarm_actions = (
    var.generation_alarm_actions
  )

  treat_missing_data = "notBreaching"
}


resource "aws_cloudwatch_metric_alarm" "learning_material_oldest_message" {
  alarm_name = (
    "${local.name}-learning-material-oldest-message"
  )

  alarm_description = "Learning Materials queue has an old unprocessed message."

  namespace = "AWS/SQS"

  metric_name = (
    "ApproximateAgeOfOldestMessage"
  )

  statistic = "Maximum"

  period = 60

  evaluation_periods = 2

  datapoints_to_alarm = 2

  comparison_operator = (
    "GreaterThanOrEqualToThreshold"
  )

  threshold = (
    var.generation_oldest_message_alarm_seconds
  )

  dimensions = {
    QueueName = (
      aws_sqs_queue.learning_material.name
    )
  }

  alarm_actions = (
    var.generation_alarm_actions
  )

  treat_missing_data = "notBreaching"
}


# ------------------------------------------------------------
# DLQ alarms
# ------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "quick_summary_dlq" {
  alarm_name = (
    "${local.name}-quick-summary-dlq"
  )

  alarm_description = "Quick Summary messages have entered the dead-letter queue."

  namespace = "AWS/SQS"

  metric_name = (
    "ApproximateNumberOfMessagesVisible"
  )

  statistic = "Maximum"

  period = 60

  evaluation_periods = 1

  comparison_operator = (
    "GreaterThanOrEqualToThreshold"
  )

  threshold = 1

  dimensions = {
    QueueName = (
      aws_sqs_queue.quick_summary_dlq.name
    )
  }

  alarm_actions = (
    var.generation_alarm_actions
  )

  treat_missing_data = "notBreaching"
}


resource "aws_cloudwatch_metric_alarm" "learning_material_dlq" {
  alarm_name = (
    "${local.name}-learning-material-dlq"
  )

  alarm_description = "Learning Materials messages have entered the dead-letter queue."

  namespace = "AWS/SQS"

  metric_name = (
    "ApproximateNumberOfMessagesVisible"
  )

  statistic = "Maximum"

  period = 60

  evaluation_periods = 1

  comparison_operator = (
    "GreaterThanOrEqualToThreshold"
  )

  threshold = 1

  dimensions = {
    QueueName = (
      aws_sqs_queue.learning_material_dlq.name
    )
  }

  alarm_actions = (
    var.generation_alarm_actions
  )

  treat_missing_data = "notBreaching"
}


# ------------------------------------------------------------
# Outputs
# ------------------------------------------------------------

output "quick_summary_queue_url" {
  value = (
    aws_sqs_queue.quick_summary.url
  )
}


output "quick_summary_dlq_url" {
  value = (
    aws_sqs_queue.quick_summary_dlq.url
  )
}


output "learning_material_queue_url" {
  value = (
    aws_sqs_queue.learning_material.url
  )
}


output "learning_material_dlq_url" {
  value = (
    aws_sqs_queue.learning_material_dlq.url
  )
}


output "generation_dispatcher_service" {
  value = (
    aws_ecs_service
    .generation_dispatcher
    .name
  )
}


output "quick_summary_service" {
  value = (
    aws_ecs_service.quick_summary.name
  )
}


output "learning_material_service" {
  value = (
    aws_ecs_service
    .learning_material
    .name
  )
}
