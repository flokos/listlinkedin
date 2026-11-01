variable "region" {
  description = "OCI region. Always Free resources must be in the home region."
  type        = string
  default     = "eu-frankfurt-1"
}

variable "oci_profile" {
  description = "Profile in ~/.oci/config used for API-key authentication."
  type        = string
  default     = "DEFAULT"
}

variable "compartment_ocid" {
  description = "OCID of the ListLinkedIn compartment."
  type        = string
}

variable "availability_domain_number" {
  description = "1, 2 or 3. A1.Flex is offered in all three Frankfurt ADs; switch on 'Out of host capacity'."
  type        = number
  default     = 1

  validation {
    condition     = contains([1, 2, 3], var.availability_domain_number)
    error_message = "availability_domain_number must be 1, 2 or 3."
  }
}

variable "ssh_public_key" {
  description = "OpenSSH public key installed for the 'ubuntu' user."
  type        = string
}

variable "admin_cidrs" {
  description = "IPv4 CIDRs allowed to reach SSH (port 22). Keep this to your own addresses."
  type        = list(string)

  validation {
    condition     = length(var.admin_cidrs) > 0 && alltrue([for c in var.admin_cidrs : can(cidrhost(c, 0)) && c != "0.0.0.0/0"])
    error_message = "admin_cidrs must be valid IPv4 CIDRs and must not include 0.0.0.0/0."
  }
}

variable "instance_ocpus" {
  description = "A1.Flex OCPUs. The Always Free allowance is 2 OCPUs in total."
  type        = number
  default     = 2

  validation {
    condition     = var.instance_ocpus >= 1 && var.instance_ocpus <= 2
    error_message = "Always Free allows at most 2 A1 OCPUs."
  }
}

variable "instance_memory_gbs" {
  description = "A1.Flex memory in GB. The Always Free allowance is 12 GB in total."
  type        = number
  default     = 12

  validation {
    condition     = var.instance_memory_gbs >= 1 && var.instance_memory_gbs <= 12
    error_message = "Always Free allows at most 12 GB of A1 memory."
  }
}

variable "boot_volume_gbs" {
  description = "Boot volume size in GB (minimum 50)."
  type        = number
  default     = 50

  validation {
    condition     = var.boot_volume_gbs >= 50
    error_message = "The boot volume must be at least 50 GB."
  }
}

variable "data_volume_gbs" {
  description = "Block volume for Docker data (PostgreSQL, media) and local backups. 0 disables it."
  type        = number
  default     = 50

  validation {
    condition     = var.data_volume_gbs == 0 || var.data_volume_gbs >= 50
    error_message = "A block volume is at least 50 GB, or 0 to disable it."
  }

  # Always Free: 200 GB of boot plus block volume storage in the home region.
  validation {
    condition     = var.boot_volume_gbs + var.data_volume_gbs <= 200
    error_message = "Boot plus block volumes exceed the 200 GB Always Free storage."
  }
}

variable "email_domain" {
  description = "Domain to send email from through OCI Email Delivery, e.g. example.com. Empty disables email resources."
  type        = string
  default     = ""
}

variable "email_sender" {
  description = "Approved sender address, e.g. no-reply@example.com. Must be in email_domain."
  type        = string
  default     = ""

  validation {
    condition     = var.email_domain == "" || endswith(lower(var.email_sender), "@${lower(var.email_domain)}")
    error_message = "email_sender must be an address in email_domain."
  }
}

variable "dkim_selector" {
  description = "DKIM selector. OCI requires it to be unique per region across all tenancies."
  type        = string
  default     = "listlinkedin-fra-202611"
}

locals {
  name = "listlinkedin"

  tags = {
    project    = "listlinkedin"
    env        = "production"
    managed-by = "terraform"
  }

  email_enabled = var.email_domain != ""
}
