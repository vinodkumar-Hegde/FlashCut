variable "aws_region" {
  type = string

  validation {
    condition = length(
      trimspace(var.aws_region)
    ) > 0

    error_message = "aws_region must be supplied explicitly."
  }
}

variable "image_tag" {
  type    = string
  default = "staging"
}

variable "api_desired_count" {
  type    = number
  default = 1
}

variable "bedrock_model_id" {
  type    = string
  default = "global.amazon.nova-2-lite-v1:0"
}

variable "transcribe_language" {
  type    = string
  default = "en-US"
}


variable "expected_aws_account_id" {
  type      = string
  sensitive = true

  validation {
    condition = can(
      regex(
        "^[0-9]{12}$",
        var.expected_aws_account_id,
      )
    )

    error_message = "expected_aws_account_id must contain exactly 12 digits."
  }
}


variable "bootstrap_mode" {
  type        = bool
  default     = true
  description = "Keep all ECS services at zero until images and database migrations are ready."
}


variable "cloudfront_aliases" {
  type        = list(string)
  default     = []
  description = "Optional custom DNS aliases for the CloudFront distribution."
}

variable "cloudfront_acm_certificate_arn" {
  type        = string
  default     = null
  nullable    = true
  description = "Optional ACM certificate ARN from us-east-1 for custom CloudFront aliases."

  validation {
    condition = (
      var.cloudfront_acm_certificate_arn == null
      || can(
        regex(
          "^arn:aws:acm:us-east-1:[0-9]{12}:certificate/.+$",
          var.cloudfront_acm_certificate_arn,
        )
      )
    )

    error_message = "cloudfront_acm_certificate_arn must be a valid us-east-1 ACM certificate ARN."
  }
}
