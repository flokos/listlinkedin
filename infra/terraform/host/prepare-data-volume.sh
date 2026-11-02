#!/bin/bash
# Mount the block volume at /srv/data. Formats it only when it has no filesystem at all.
# The expected size in bytes is in /etc/listlinkedin/data-volume-bytes (0: no volume).
set -euo pipefail
size=$(cat /etc/listlinkedin/data-volume-bytes)
mkdir -p /srv/data
if [ "$size" -eq 0 ]; then echo "no data volume configured; /srv/data stays on the boot volume"; exit 0; fi
if mountpoint -q /srv/data; then echo "/srv/data already mounted"; exit 0; fi
# The disk holding / is never a candidate, even when it has the same size as the data volume.
root_disk=/dev/$(lsblk -no PKNAME "$(findmnt -no SOURCE /)")

# A blank disk: the expected size, not the root disk, no partitions, no partition table and
# no filesystem. Anything else is left alone.
blank_disk() {
  lsblk -dnbo NAME,SIZE,TYPE | while read -r name bytes type; do
    dev=/dev/$name
    [ "$type" = disk ] && [ "$bytes" = "$size" ] && [ "$dev" != "$root_disk" ] || continue
    [ "$(lsblk -n -o NAME "$dev" | wc -l)" -eq 1 ] || continue
    [ -z "$(blkid -p -o value -s PTTYPE "$dev" 2>/dev/null)" ] || continue
    [ -z "$(blkid -p -o value -s TYPE "$dev" 2>/dev/null)" ] || continue
    echo "$dev"
  done | head -n 1
}

dev=""
for _ in $(seq 1 180); do   # Terraform attaches the volume after the instance boots
  if blkid -L llidata >/dev/null 2>&1; then dev=$(blkid -L llidata); break; fi
  dev=$(blank_disk)
  [ -n "$dev" ] && break
  sleep 5
done
[ -n "$dev" ] || { echo "no blank ${size}-byte data volume found after 15 minutes" >&2; exit 1; }
if ! blkid -L llidata >/dev/null 2>&1; then
  echo "formatting $dev as llidata"
  mkfs.ext4 -q -L llidata "$dev"
fi
grep -q 'LABEL=llidata' /etc/fstab || echo 'LABEL=llidata /srv/data ext4 defaults,nofail,x-systemd.device-timeout=60s 0 2' >> /etc/fstab
systemctl daemon-reload
mount /srv/data
