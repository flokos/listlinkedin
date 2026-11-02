output "public_ip" {
  description = "Reserved public IPv4 address. Point the DNS A record here."
  value       = oci_core_public_ip.app.ip_address
}

output "ssh" {
  description = "SSH command (from an address in admin_cidrs)."
  value       = "ssh ubuntu@${oci_core_public_ip.app.ip_address}"
}

output "image" {
  description = "Image the instance was created from."
  value       = data.oci_core_images.ubuntu_arm.images[0].display_name
}

output "availability_domain" {
  value = local.availability_domain
}

output "smtp_endpoint" {
  description = "SMTP relay for EMAIL_HOST (port 587, STARTTLS)."
  value       = "smtp.email.${var.region}.oci.oraclecloud.com"
}

output "dkim_dns_record" {
  description = "CNAME to publish for DKIM, when email is enabled."
  value = local.email_enabled ? {
    name  = oci_email_dkim.main[0].dns_subdomain_name
    type  = "CNAME"
    value = oci_email_dkim.main[0].cname_record_value
  } : null
}

output "spf_dns_record" {
  description = "SPF TXT record for the sending domain, when email is enabled."
  value = local.email_enabled ? {
    name  = lower(var.email_domain)
    type  = "TXT"
    value = "v=spf1 include:eu.rp.oracleemaildelivery.com ~all"
  } : null
}
