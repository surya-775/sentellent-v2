terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  # Remote state — create this S3 bucket + DynamoDB table once manually (or via a bootstrap script)
  # before running `terraform init`, since Terraform can't create its own backend.
  backend "s3" {
    bucket         = "sentellent-stock-analyst-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "sentellent-tfstate-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}
