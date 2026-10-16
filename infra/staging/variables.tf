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
