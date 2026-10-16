data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "all_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}


locals {
  name = "flashcut-staging"

  azs = slice(
    data.aws_availability_zones.available.names,
    0,
    2,
  )

  bucket_name = lower(
    "flashcut-staging-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  )
}


# --------------------------------------------------
# Network
# --------------------------------------------------

resource "aws_vpc" "main" {
  cidr_block = "10.90.0.0/16"

  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "${local.name}-vpc"
    Environment = "staging"
    Application = "DT-FlashCut"
  }
}


resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name}-igw"
  }
}


resource "aws_subnet" "public" {
  count = 2

  vpc_id = aws_vpc.main.id

  availability_zone = local.azs[count.index]

  cidr_block = cidrsubnet(
    aws_vpc.main.cidr_block,
    8,
    count.index,
  )

  map_public_ip_on_launch = true

  tags = {
    Name = "${local.name}-public-${count.index + 1}"
  }
}


resource "aws_subnet" "private" {
  count = 2

  vpc_id = aws_vpc.main.id

  availability_zone = local.azs[count.index]

  cidr_block = cidrsubnet(
    aws_vpc.main.cidr_block,
    8,
    10 + count.index,
  )

  tags = {
    Name = "${local.name}-private-${count.index + 1}"
  }
}


resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
}


resource "aws_route" "public_internet" {
  route_table_id = aws_route_table.public.id

  destination_cidr_block = "0.0.0.0/0"

  gateway_id = aws_internet_gateway.main.id
}


resource "aws_route_table_association" "public" {
  count = 2

  subnet_id = aws_subnet.public[count.index].id

  route_table_id = aws_route_table.public.id
}


resource "aws_eip" "nat" {
  domain = "vpc"

  depends_on = [
    aws_internet_gateway.main,
  ]

  tags = {
    Name = "${local.name}-nat"
  }
}


resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id

  subnet_id = aws_subnet.public[0].id

  depends_on = [
    aws_internet_gateway.main,
  ]

  tags = {
    Name = "${local.name}-nat"
  }
}


resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
}


resource "aws_route" "private_internet" {
  route_table_id = aws_route_table.private.id

  destination_cidr_block = "0.0.0.0/0"

  nat_gateway_id = aws_nat_gateway.main.id
}


resource "aws_route_table_association" "private" {
  count = 2

  subnet_id = aws_subnet.private[count.index].id

  route_table_id = aws_route_table.private.id
}


# --------------------------------------------------
# Security groups
# --------------------------------------------------

resource "aws_security_group" "alb" {
  name = "${local.name}-alb"

  vpc_id = aws_vpc.main.id

  ingress {
    from_port = 80
    to_port   = 80
    protocol  = "tcp"

    prefix_list_ids = [
      data.aws_ec2_managed_prefix_list.cloudfront.id,
    ]
  }

  egress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"

    cidr_blocks = [
      "0.0.0.0/0",
    ]
  }
}


resource "aws_security_group" "tasks" {
  name = "${local.name}-tasks"

  vpc_id = aws_vpc.main.id

  ingress {
    from_port = 5001
    to_port   = 5001
    protocol  = "tcp"

    security_groups = [
      aws_security_group.alb.id,
    ]
  }

  egress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"

    cidr_blocks = [
      "0.0.0.0/0",
    ]
  }
}


resource "aws_security_group" "database" {
  name = "${local.name}-database"

  vpc_id = aws_vpc.main.id

  ingress {
    from_port = 5432
    to_port   = 5432
    protocol  = "tcp"

    security_groups = [
      aws_security_group.tasks.id,
    ]
  }

  egress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"

    cidr_blocks = [
      "0.0.0.0/0",
    ]
  }
}


resource "aws_security_group" "redis" {
  name = "${local.name}-redis"

  vpc_id = aws_vpc.main.id

  ingress {
    from_port = 6379
    to_port   = 6379
    protocol  = "tcp"

    security_groups = [
      aws_security_group.tasks.id,
    ]
  }

  egress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"

    cidr_blocks = [
      "0.0.0.0/0",
    ]
  }
}


# --------------------------------------------------
# S3
# --------------------------------------------------

resource "aws_s3_bucket" "staging" {
  bucket = local.bucket_name

  force_destroy = true

  tags = {
    Environment = "staging"
    Application = "DT-FlashCut"
  }
}


resource "aws_s3_bucket_public_access_block" "staging" {
  bucket = aws_s3_bucket.staging.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


resource "aws_s3_bucket_versioning" "staging" {
  bucket = aws_s3_bucket.staging.id

  versioning_configuration {
    status = "Enabled"
  }
}


resource "aws_s3_bucket_server_side_encryption_configuration" "staging" {
  bucket = aws_s3_bucket.staging.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}


# --------------------------------------------------
# SQS
# --------------------------------------------------

resource "aws_sqs_queue" "render_dlq" {
  name = "${local.name}-render-dlq"

  message_retention_seconds = 1209600

  sqs_managed_sse_enabled = true
}


resource "aws_sqs_queue" "render" {
  name = "${local.name}-render"

  visibility_timeout_seconds = 300

  message_retention_seconds = 345600

  sqs_managed_sse_enabled = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.render_dlq.arn
    maxReceiveCount     = 5
  })
}


# --------------------------------------------------
# RDS PostgreSQL
# --------------------------------------------------

resource "random_password" "database" {
  length  = 32
  special = false
}


resource "aws_db_subnet_group" "main" {
  name = "${local.name}-db"

  subnet_ids = aws_subnet.private[*].id
}


resource "aws_db_instance" "database" {
  identifier = "${local.name}-postgres"

  engine         = "postgres"
  engine_version = "17"

  instance_class = "db.t4g.micro"

  allocated_storage     = 20
  max_allocated_storage = 50
  storage_type          = "gp3"

  storage_encrypted = true

  db_name  = "flashcut"
  username = "flashcut"
  password = random_password.database.result

  port = 5432

  db_subnet_group_name = aws_db_subnet_group.main.name

  vpc_security_group_ids = [
    aws_security_group.database.id,
  ]

  publicly_accessible = false

  backup_retention_period = 7

  auto_minor_version_upgrade = true
  apply_immediately          = true

  multi_az = false

  deletion_protection = false
  skip_final_snapshot = true

  tags = {
    Environment = "staging"
    Application = "DT-FlashCut"
  }
}


resource "aws_secretsmanager_secret" "database_url" {
  name = "flashcut/staging/database-url"
}


resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id

  secret_string = format(
    "postgresql+psycopg://flashcut:%s@%s:5432/flashcut",
    urlencode(random_password.database.result),
    aws_db_instance.database.address,
  )
}


# --------------------------------------------------
# ElastiCache Redis
# --------------------------------------------------

resource "random_password" "redis" {
  length  = 32
  special = false
}


resource "aws_elasticache_subnet_group" "main" {
  name = "${local.name}-redis"

  subnet_ids = aws_subnet.private[*].id
}


resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${local.name}-redis"

  description = "DT-FlashCut staging Redis"

  engine = "redis"

  node_type = "cache.t4g.micro"

  port = 6379

  num_cache_clusters = 1

  subnet_group_name = aws_elasticache_subnet_group.main.name

  security_group_ids = [
    aws_security_group.redis.id,
  ]

  at_rest_encryption_enabled = true

  transit_encryption_enabled = true

  auth_token = random_password.redis.result

  automatic_failover_enabled = false

  multi_az_enabled = false

  apply_immediately = true
}


resource "aws_secretsmanager_secret" "redis_url" {
  name = "flashcut/staging/redis-url"
}


resource "aws_secretsmanager_secret_version" "redis_url" {
  secret_id = aws_secretsmanager_secret.redis_url.id

  secret_string = format(
    "rediss://:%s@%s:6379/0",
    urlencode(random_password.redis.result),
    aws_elasticache_replication_group.redis.primary_endpoint_address,
  )
}


# --------------------------------------------------
# Cognito tenant authentication
# --------------------------------------------------

resource "aws_iam_role" "pretoken" {
  name = "${local.name}-pretoken"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "lambda.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}


resource "aws_iam_role_policy_attachment" "pretoken_logs" {
  role = aws_iam_role.pretoken.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}


data "archive_file" "pretoken" {
  type = "zip"

  source_file = "${path.module}/pretoken.py"

  output_path = "${path.module}/build/pretoken.zip"
}


resource "aws_lambda_function" "pretoken" {
  function_name = "${local.name}-pretoken"

  role = aws_iam_role.pretoken.arn

  runtime = "python3.13"

  handler = "pretoken.handler"

  filename = data.archive_file.pretoken.output_path

  source_code_hash = data.archive_file.pretoken.output_base64sha256
}


resource "aws_lambda_permission" "cognito" {
  statement_id = "AllowCognito"

  action = "lambda:InvokeFunction"

  function_name = aws_lambda_function.pretoken.function_name

  principal = "cognito-idp.amazonaws.com"

  source_account = data.aws_caller_identity.current.account_id
}


resource "aws_cognito_user_pool" "main" {
  name = "${local.name}-users"

  username_attributes = [
    "email",
  ]

  auto_verified_attributes = []

  password_policy {
    minimum_length = 12

    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  schema {
    name = "tenant_id"

    attribute_data_type = "String"

    mutable  = true
    required = false

    string_attribute_constraints {
      min_length = 1
      max_length = 128
    }
  }

  lambda_config {
    pre_token_generation_config {
      lambda_arn = aws_lambda_function.pretoken.arn

      lambda_version = "V2_0"
    }
  }

  depends_on = [
    aws_lambda_permission.cognito,
  ]
}


resource "aws_cognito_user_pool_client" "main" {
  name = "${local.name}-client"

  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = false

  prevent_user_existence_errors = "ENABLED"

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  access_token_validity = 60

  id_token_validity = 60

  refresh_token_validity = 1

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}


# --------------------------------------------------
# ECR
# --------------------------------------------------

resource "aws_ecr_repository" "api" {
  name = "${local.name}-api"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}


resource "aws_ecr_repository" "render" {
  name = "${local.name}-render"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}


resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1

        description = "Keep latest ten images"

        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }

        action = {
          type = "expire"
        }
      }
    ]
  })
}


resource "aws_ecr_lifecycle_policy" "render" {
  repository = aws_ecr_repository.render.name

  policy = aws_ecr_lifecycle_policy.api.policy
}


# --------------------------------------------------
# IAM for ECS
# --------------------------------------------------

resource "aws_iam_role" "ecs_execution" {
  name = "${local.name}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}


resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role = aws_iam_role.ecs_execution.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}


resource "aws_iam_role_policy" "ecs_execution_secrets" {
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "secretsmanager:GetSecretValue"
        ]

        Resource = [
          aws_secretsmanager_secret.database_url.arn,
          aws_secretsmanager_secret.redis_url.arn,
        ]
      }
    ]
  })
}


resource "aws_iam_role" "ecs_task" {
  name = "${local.name}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}


resource "aws_iam_role_policy" "ecs_task" {
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]

        Resource = [
          aws_s3_bucket.staging.arn
        ]
      },

      {
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:DeleteObject"
        ]

        Resource = [
          "${aws_s3_bucket.staging.arn}/*"
        ]
      },

      {
        Effect = "Allow"

        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]

        Resource = [
          aws_sqs_queue.render.arn,
          aws_sqs_queue.render_dlq.arn,
        ]
      },

      {
        Effect = "Allow"

        Action = [
          "transcribe:StartTranscriptionJob",
          "transcribe:GetTranscriptionJob"
        ]

        Resource = "*"
      },

      {
        Effect = "Allow"

        Action = [
          "bedrock:InvokeModel"
        ]

        Resource = "*"
      }
    ]
  })
}


# --------------------------------------------------
# CloudWatch
# --------------------------------------------------

resource "aws_cloudwatch_log_group" "api" {
  name = "/flashcut/staging/api"

  retention_in_days = 14
}


resource "aws_cloudwatch_log_group" "summary" {
  name = "/flashcut/staging/summary"

  retention_in_days = 14
}


resource "aws_cloudwatch_log_group" "notes" {
  name = "/flashcut/staging/notes"

  retention_in_days = 14
}


resource "aws_cloudwatch_log_group" "render" {
  name = "/flashcut/staging/render"

  retention_in_days = 14
}


# --------------------------------------------------
# Load balancer
# --------------------------------------------------

resource "aws_lb" "api" {
  name = "flashcut-staging"

  internal = false

  load_balancer_type = "application"

  security_groups = [
    aws_security_group.alb.id,
  ]

  subnets = aws_subnet.public[*].id

  enable_deletion_protection = false
}


resource "aws_lb_target_group" "api" {
  name = "flashcut-staging-api"

  port     = 5001
  protocol = "HTTP"

  target_type = "ip"

  vpc_id = aws_vpc.main.id

  deregistration_delay = 15

  health_check {
    enabled = true

    path = "/health/ready"

    healthy_threshold   = 2
    unhealthy_threshold = 3

    interval = 30
    timeout  = 10

    matcher = "200"
  }
}


resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.api.arn

  port     = 80
  protocol = "HTTP"

  default_action {
    type = "forward"

    target_group_arn = aws_lb_target_group.api.arn
  }
}


# --------------------------------------------------
# CloudFront HTTPS endpoint
# --------------------------------------------------

resource "aws_cloudfront_distribution" "api" {
  enabled = true

  comment = "DT-FlashCut staging API"

  origin {
    domain_name = aws_lb.api.dns_name

    origin_id = "flashcut-staging-alb"

    custom_origin_config {
      http_port  = 80
      https_port = 443

      origin_protocol_policy = "http-only"

      origin_ssl_protocols = [
        "TLSv1.2",
      ]
    }
  }

  default_cache_behavior {
    target_origin_id = "flashcut-staging-alb"

    viewer_protocol_policy = "redirect-to-https"

    allowed_methods = [
      "DELETE",
      "GET",
      "HEAD",
      "OPTIONS",
      "PATCH",
      "POST",
      "PUT",
    ]

    cached_methods = [
      "GET",
      "HEAD",
    ]

    cache_policy_id = data.aws_cloudfront_cache_policy.disabled.id

    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_except_host.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true

    minimum_protocol_version = "TLSv1.2_2021"
  }

  price_class = "PriceClass_200"
}


# --------------------------------------------------
# ECS
# --------------------------------------------------

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}


locals {
  auth_issuer = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"

  common_environment = [
    {
      name  = "APP_ENV"
      value = "production"
    },
    {
      name  = "APP_VERSION"
      value = "1.0.0"
    },
    {
      name  = "AUTH_DISABLED"
      value = "false"
    },
    {
      name  = "AUTH_JWT_ISSUER"
      value = local.auth_issuer
    },
    {
      name  = "AUTH_JWT_AUDIENCE"
      value = aws_cognito_user_pool_client.main.id
    },
    {
      name  = "AUTH_TENANT_CLAIM"
      value = "custom:tenant_id"
    },
    {
      name  = "AUTH_SUBJECT_CLAIM"
      value = "sub"
    },
    {
      name  = "AUTH_JWT_AUDIENCE_CLAIM"
      value = "client_id"
    },
    {
      name  = "AUTH_JWT_TOKEN_USE"
      value = "access"
    },
    {
      name  = "AUTH_JWT_ALGORITHMS"
      value = "RS256"
    },
    {
      name  = "RATE_LIMIT_ENABLED"
      value = "true"
    },
    {
      name  = "TRUSTED_HOSTS"
      value = aws_lb.api.dns_name
    },
    {
      name  = "AWS_REGION"
      value = var.aws_region
    },
    {
      name  = "AWS_DEFAULT_REGION"
      value = var.aws_region
    },
    {
      name  = "S3_BUCKET"
      value = aws_s3_bucket.staging.bucket
    },
    {
      name  = "S3_VIDEO_PREFIX"
      value = "videos/"
    },
    {
      name  = "S3_TENANT_PREFIX_TEMPLATE"
      value = "videos/tenants/{tenant_id}/"
    },
    {
      name  = "S3_OUTPUT_PREFIX"
      value = "generated/"
    },
    {
      name  = "S3_TRANSCRIPT_PREFIX"
      value = "transcripts/"
    },
    {
      name  = "TRANSCRIBE_LANGUAGE"
      value = var.transcribe_language
    },
    {
      name  = "BEDROCK_REGION"
      value = var.aws_region
    },
    {
      name  = "BEDROCK_MODEL_ID"
      value = var.bedrock_model_id
    },
    {
      name  = "RENDER_QUEUE_URL"
      value = aws_sqs_queue.render.url
    },
    {
      name  = "MAX_REQUEST_BYTES"
      value = "2000000"
    },

    {
      name = "QUICK_SUMMARY_QUEUE_URL"

      value = (
        aws_sqs_queue.quick_summary.url
      )
    },

    {
      name = "LEARNING_MATERIAL_QUEUE_URL"

      value = (
        aws_sqs_queue.learning_material.url
      )
    },

    {
      name  = "GENERATION_VISIBILITY_TIMEOUT_SECONDS"
      value = "300"
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

  common_secrets = [
    {
      name      = "DATABASE_URL"
      valueFrom = aws_secretsmanager_secret.database_url.arn
    },
    {
      name      = "REDIS_URL"
      valueFrom = aws_secretsmanager_secret.redis_url.arn
    }
  ]
}


resource "aws_ecs_task_definition" "api" {
  family = "${local.name}-api"

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = "256"
  memory = "512"

  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name = "api"

      image = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"

      essential = true

      portMappings = [
        {
          containerPort = 5001
          hostPort      = 5001
          protocol      = "tcp"
        }
      ]

      environment = local.common_environment

      secrets = local.common_secrets

      command = [
        "sh",
        "-c",
        "alembic -c /app/alembic.ini upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 5001 --no-access-log",
      ]

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])

  depends_on = [
    aws_secretsmanager_secret_version.database_url,
    aws_secretsmanager_secret_version.redis_url,
  ]
}


resource "aws_ecs_task_definition" "summary" {
  family = "${local.name}-summary"

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = "256"
  memory = "512"

  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name = "summary"

      image = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"

      essential = true

      environment = local.common_environment

      secrets = local.common_secrets

      command = [
        "python",
        "-m",
        "app.workers.summary_worker",
      ]

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group         = aws_cloudwatch_log_group.summary.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "summary"
        }
      }
    }
  ])
}


resource "aws_ecs_task_definition" "notes" {
  family = "${local.name}-notes"

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = "256"
  memory = "512"

  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name = "notes"

      image = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"

      essential = true

      environment = local.common_environment

      secrets = local.common_secrets

      command = [
        "python",
        "-m",
        "app.workers.notes_worker",
      ]

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group         = aws_cloudwatch_log_group.notes.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "notes"
        }
      }
    }
  ])
}


resource "aws_ecs_task_definition" "render" {
  family = "${local.name}-render"

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu    = "1024"
  memory = "2048"

  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  ephemeral_storage {
    size_in_gib = 40
  }

  container_definitions = jsonencode([
    {
      name = "render"

      image = "${aws_ecr_repository.render.repository_url}:${var.image_tag}"

      essential = true

      environment = local.common_environment

      secrets = local.common_secrets

      command = [
        "python",
        "-m",
        "app.workers.render_worker",
      ]

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group         = aws_cloudwatch_log_group.render.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "render"
        }
      }
    }
  ])
}


resource "aws_ecs_service" "api" {
  name = "${local.name}-api"

  cluster = aws_ecs_cluster.main.id

  task_definition = aws_ecs_task_definition.api.arn

  desired_count = var.api_desired_count

  launch_type = "FARGATE"

  network_configuration {
    subnets = aws_subnet.private[*].id

    security_groups = [
      aws_security_group.tasks.id,
    ]

    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn

    container_name = "api"
    container_port = 5001
  }

  depends_on = [
    aws_lb_listener.api,
  ]
}


resource "aws_ecs_service" "summary" {
  name = "${local.name}-summary"

  cluster = aws_ecs_cluster.main.id

  task_definition = aws_ecs_task_definition.summary.arn

  desired_count = 1

  launch_type = "FARGATE"

  network_configuration {
    subnets = aws_subnet.private[*].id

    security_groups = [
      aws_security_group.tasks.id,
    ]

    assign_public_ip = false
  }
}


resource "aws_ecs_service" "notes" {
  name = "${local.name}-notes"

  cluster = aws_ecs_cluster.main.id

  task_definition = aws_ecs_task_definition.notes.arn

  desired_count = 1

  launch_type = "FARGATE"

  network_configuration {
    subnets = aws_subnet.private[*].id

    security_groups = [
      aws_security_group.tasks.id,
    ]

    assign_public_ip = false
  }
}


resource "aws_ecs_service" "render" {
  name = "${local.name}-render"

  cluster = aws_ecs_cluster.main.id

  task_definition = aws_ecs_task_definition.render.arn

  desired_count = 1

  launch_type = "FARGATE"

  network_configuration {
    subnets = aws_subnet.private[*].id

    security_groups = [
      aws_security_group.tasks.id,
    ]

    assign_public_ip = false
  }
}


# --------------------------------------------------
# Outputs
# --------------------------------------------------

output "api_ecr_url" {
  value = aws_ecr_repository.api.repository_url
}


output "render_ecr_url" {
  value = aws_ecr_repository.render.repository_url
}


output "staging_bucket" {
  value = aws_s3_bucket.staging.bucket
}


output "render_queue_url" {
  value = aws_sqs_queue.render.url
}


output "ecs_cluster" {
  value = aws_ecs_cluster.main.name
}


output "api_service" {
  value = aws_ecs_service.api.name
}


output "summary_service" {
  value = aws_ecs_service.summary.name
}


output "notes_service" {
  value = aws_ecs_service.notes.name
}


output "render_service" {
  value = aws_ecs_service.render.name
}


output "user_pool_id" {
  value = aws_cognito_user_pool.main.id
}


output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.main.id
}


output "staging_url" {
  value = "https://${aws_cloudfront_distribution.api.domain_name}"
}
