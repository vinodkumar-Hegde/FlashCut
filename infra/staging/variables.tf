variable "aws_region" {
  type    = string
  default = "ap-south-1"
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
