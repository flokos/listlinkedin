# Docker's data root (the pgdata and media volumes) and local backups live on a block volume,
# so the database survives rebuilding the instance. cloud-init formats it on first use only.

resource "oci_core_volume" "data" {
  count = var.data_volume_gbs > 0 ? 1 : 0

  compartment_id      = var.compartment_ocid
  availability_domain = local.availability_domain
  display_name        = "${local.name}-prod-data"
  size_in_gbs         = var.data_volume_gbs
  vpus_per_gb         = 10
  freeform_tags       = local.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "oci_core_volume_attachment" "data" {
  count = var.data_volume_gbs > 0 ? 1 : 0

  attachment_type = "paravirtualized"
  instance_id     = oci_core_instance.app.id
  volume_id       = oci_core_volume.data[0].id
  display_name    = "${local.name}-prod-data"
}
