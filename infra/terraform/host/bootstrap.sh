#!/bin/bash
# First-boot setup of the listlinkedin production host (Ubuntu 24.04, arm64), run by
# cloud-init. Safe to run again by hand: sudo /usr/local/sbin/lli-bootstrap
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt_opts=(-y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)

timedatectl set-timezone Etc/UTC
apt-get update
apt-get "${apt_opts[@]}" upgrade
apt-get "${apt_opts[@]}" install ca-certificates curl git unattended-upgrades

# Ubuntu's OCI images reject all inbound but SSH in iptables. Open 80/443, and save the rules
# only while Docker isn't installed, so the saved rules never contain Docker's chains.
if ! iptables -C INPUT -p tcp -m state --state NEW -m multiport --dports 80,443 -j ACCEPT 2>/dev/null; then
  iptables -I INPUT -p tcp -m state --state NEW -m multiport --dports 80,443 -j ACCEPT
  command -v docker >/dev/null || netfilter-persistent save
fi

# Stop here rather than let Docker put the database on the boot volume.
/usr/local/sbin/lli-prepare-data-volume

mkdir -p /srv/data/backups /srv/listlinkedin /var/backups
ln -sfn /srv/data/backups /var/backups/listlinkedin
chown ubuntu:ubuntu /srv/listlinkedin

# Rootful Docker Engine and the Compose plugin from Docker's apt repository (docs/deployment.md).
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<SOURCES
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
SOURCES
apt-get update
apt-get "${apt_opts[@]}" install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker ubuntu
systemctl daemon-reload
systemctl enable --now docker
docker info --format 'Docker {{.ServerVersion}}, data root {{.DockerRootDir}}'
touch /var/lib/cloud/instance/listlinkedin-ready 2>/dev/null || true
echo "listlinkedin host ready"
