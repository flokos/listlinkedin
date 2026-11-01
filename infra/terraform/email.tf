# OCI Email Delivery: a sending domain with DKIM and one approved sender. Created only when
# email_domain is set. The SMTP credential is not managed here, so its password never enters
# Terraform state; see README.md.

resource "oci_email_email_domain" "main" {
  count = local.email_enabled ? 1 : 0

  compartment_id = var.compartment_ocid
  name           = lower(var.email_domain)
  description    = "listlinkedin production mail"
  freeform_tags  = local.tags
}

resource "oci_email_dkim" "main" {
  count = local.email_enabled ? 1 : 0

  email_domain_id = oci_email_email_domain.main[0].id
  name            = var.dkim_selector
  description     = "listlinkedin production DKIM"
  freeform_tags   = local.tags
}

resource "oci_email_sender" "main" {
  count = local.email_enabled ? 1 : 0

  compartment_id = var.compartment_ocid
  email_address  = lower(var.email_sender)
  freeform_tags  = local.tags

  depends_on = [oci_email_email_domain.main]
}
