data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_ocid
}

# The newest standard (not Minimal) Ubuntu 24.04 image for Arm.
data "oci_core_images" "ubuntu_arm" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"

  filter {
    name   = "display_name"
    values = ["^Canonical-Ubuntu-24\\.04-aarch64-.*"]
    regex  = true
  }
}

locals {
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[var.availability_domain_number - 1].name
}

resource "oci_core_instance" "app" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.availability_domain
  display_name        = "${local.name}-prod"
  shape               = "VM.Standard.A1.Flex"
  freeform_tags       = local.tags

  shape_config {
    ocpus         = var.instance_ocpus
    memory_in_gbs = var.instance_memory_gbs
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu_arm.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_gbs
    boot_volume_vpus_per_gb = 10 # Balanced: the performance level Always Free covers
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    nsg_ids          = [oci_core_network_security_group.app.id]
    hostname_label   = "app"
    assign_public_ip = false # the reserved IP below is attached instead
  }

  instance_options {
    are_legacy_imds_endpoints_disabled = true
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tftpl", {
      data_volume_bytes   = var.data_volume_gbs * 1024 * 1024 * 1024
      daemon_json         = file("${path.module}/host/daemon.json")
      docker_dropin       = file("${path.module}/host/docker-data-volume.conf")
      prepare_data_volume = file("${path.module}/host/prepare-data-volume.sh")
      container_egress    = file("${path.module}/host/container-egress.sh")
      egress_unit         = file("${path.module}/host/listlinkedin-egress.service")
      bootstrap           = file("${path.module}/host/bootstrap.sh")
    }))
  }

  lifecycle {
    # A newer image or an edited cloud-init must not replace the running server.
    ignore_changes = [source_details[0].source_id, metadata["user_data"]]
  }
}

data "oci_core_vnic_attachments" "app" {
  compartment_id = var.compartment_ocid
  instance_id    = oci_core_instance.app.id
}

data "oci_core_private_ips" "app" {
  vnic_id = data.oci_core_vnic_attachments.app.vnic_attachments[0].vnic_id
}

# A reserved address survives replacing the instance, so DNS keeps pointing at it.
resource "oci_core_public_ip" "app" {
  compartment_id = var.compartment_ocid
  display_name   = "${local.name}-prod-ip"
  lifetime       = "RESERVED"
  private_ip_id  = data.oci_core_private_ips.app.private_ips[0].id
  freeform_tags  = local.tags

  lifecycle {
    prevent_destroy = true
  }
}
