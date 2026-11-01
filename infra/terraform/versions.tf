terraform {
  required_version = ">= 1.14.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 9.11"
    }
  }

  # State stays local (gitignored) until the deployers group may manage Object Storage.
  # Then move it to an OCI bucket with the native "oci" backend (see README.md).
}

provider "oci" {
  region              = var.region
  config_file_profile = var.oci_profile
}
