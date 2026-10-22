
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.115.0, < 2.0.0"
    }
  }
}

provider "databricks" {}
