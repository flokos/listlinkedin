# Production infrastructure (Oracle Cloud, Terraform)

Terraform for the single production host described in [docs/deployment.md](../../docs/deployment.md),
on Oracle Cloud Infrastructure's Always Free tier in `eu-frankfurt-1`
([ADR-017](../../docs/v2/adr/ADR-017-production-on-oci-always-free.md)). It creates the server
and its network; deploying the app on it follows [First deploy](../../docs/deployment.md#first-deploy).

## What it creates

| Resource | Details | Always Free allowance |
|---|---|---|
| VCN `10.20.0.0/16`, public subnet `10.20.1.0/24`, internet gateway, default route table | IPv4 | 2 VCNs |
| Default security list | Egress only, plus ICMP 3/4 (Path MTU). Replaces OCI's default rule that opens SSH to everyone | — |
| NSG on the instance | In: TCP 80 and 443 from anywhere, TCP 22 from `admin_cidrs` only. Out: all | — |
| Instance `VM.Standard.A1.Flex` | 2 OCPU, 12 GB, Ubuntu 24.04 aarch64, legacy IMDS endpoints off | 2 OCPU, 12 GB in total |
| Boot volume | 50 GB, Balanced (10 VPU/GB) | 200 GB of boot + block in total |
| Block volume (`data_volume_gbs`, default 50 GB) | Mounted at `/srv/data`: Docker's data root (`pgdata`, `media`) and `/var/backups/listlinkedin` | (same 200 GB) |
| Reserved public IPv4 | Survives replacing the instance; point DNS here | no charge |
| Email Delivery domain, DKIM, approved sender | Only when `email_domain` is set | 3,000 emails/month |

Variable validations refuse a plan beyond 2 OCPU, 12 GB or 200 GB of storage. The data volume
and the reserved IP have `prevent_destroy`.

cloud-init (first boot only) installs the files in [host/](host/) and runs
[host/bootstrap.sh](host/bootstrap.sh). It opens 80/443 in Ubuntu's host firewall, formats the
data volume if and only if it is blank (never the root disk, never a disk with partitions or a
filesystem), and installs rootful Docker Engine with the Compose plugin. It does not clone the
code or start the stack: that needs `.env` secrets and a certificate. When it is done,
`/var/lib/cloud/instance/listlinkedin-ready` exists. The scripts are safe to rerun:
`sudo /usr/local/sbin/lli-bootstrap`. Terraform ignores later edits to them on a running
instance (they would replace it); copy them over and rerun instead.

## Running it

Terraform runs in Docker ([tf.sh](tf.sh)), with `~/.oci` mounted read-only. API-key
authentication uses the `DEFAULT` profile of `~/.oci/config`.

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # compartment, SSH public key, your IP; chmod 600
./tf.sh init
./tf.sh plan -out=prod.tfplan
./tf.sh apply prod.tfplan                       # only after the plan was reviewed
```

State is local (`terraform.tfstate`, gitignored) until the deployer group may manage Object
Storage; then move it to a bucket with the native `oci` backend and `./tf.sh init -migrate-state`.
Keep a copy of the state file somewhere safe meanwhile: it is the only record of what
Terraform manages.

**Out of host capacity:** A1 capacity in Frankfurt is sometimes exhausted. Retry later, or set
`availability_domain_number` to 2 or 3 (before the first apply; moving later replaces the
instance and needs the volume moved too).

## After apply

1. Point the DNS A record of the public hostname at the `public_ip` output.
2. `ssh ubuntu@<public_ip>`, wait for `cloud-init status --wait`, then follow
   [First deploy](../../docs/deployment.md#first-deploy) in `/srv/listlinkedin`.
3. Restrict the worker's egress as [14 Worker egress](../../docs/v2/14-INFRASTRUCTURE.md#worker-egress)
   shows. The VCN (`10.20.0.0/16`) is inside the blocked `10.0.0.0/8`.
4. Backups land on the data volume (`/var/backups/listlinkedin`). Copy them off the server too:
   the same volume holds the database.

## Host jobs and hardening

- **Container egress:** [host/container-egress.sh](host/container-egress.sh), run by
  `listlinkedin-egress.service` whenever Docker starts, drops new connections from containers
  to private, link-local (metadata) and CGNAT addresses outside the host. Traffic between
  containers is not matched ([14 Worker egress](../../docs/v2/14-INFRASTRUCTURE.md#worker-egress)).
- **After the first deploy**, install [host/alert.sh](host/alert.sh) as `/usr/local/sbin/lli-alert`
  and [host/listlinkedin.cron](host/listlinkedin.cron) as `/etc/cron.d/listlinkedin`: the daily
  backup (02:30 UTC) and autoheal every 2 minutes, both alerting `MODERATION_EMAIL` through the
  app's SMTP relay.
- Certificate renewal: `/usr/local/sbin/lli-renew-cert`, daily from `/etc/cron.d/listlinkedin-cert`.

## Continuous deployment

Publishing a GitHub Release deploys it ([ADR-018](../../docs/v2/adr/ADR-018-pull-based-deployment.md)).
Install [host/auto-deploy.sh](host/auto-deploy.sh) as `/usr/local/sbin/lli-auto-deploy` and
enable [listlinkedin-deploy.timer](host/listlinkedin-deploy.timer) with its service:

```bash
sudo install -m 0755 auto-deploy.sh /usr/local/sbin/lli-auto-deploy
sudo install -m 0644 listlinkedin-deploy.service listlinkedin-deploy.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now listlinkedin-deploy.timer
```

- Every 5 minutes it compares GitHub's latest release with `/var/lib/listlinkedin/deployed-tag`.
- It deploys only `vX.Y.Z` tags on `main` that contain the running version, and skips releases
  whose notes contain `[manual-deploy]`. Skips and failures are mailed once.
- `sudo lli-auto-deploy v2.3.0` deploys a tag by hand, including a retry or a deliberate
  downgrade (restore the matching backup yourself for a downgrade).
- Logs: `journalctl -u listlinkedin-deploy` and `/var/lib/listlinkedin/deploy-<tag>.log`.
- The deployer itself isn't updated by a release: reinstall the script when it changes.

## Email

With `email_domain` and `email_sender` set, apply creates the domain, a DKIM key and the
approved sender. Then:

1. Publish the `dkim_dns_record` (CNAME) and `spf_dns_record` (TXT) outputs at your DNS host,
   and wait until the console shows DKIM as active.
2. Create an SMTP credential for the sending user (Console → user → SMTP credentials, or
   `oci iam smtp-credential create`). It is shown once. Put it straight into the server's `.env`
   as `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD`, never into Git or Terraform state.
3. `EMAIL_HOST` = the `smtp_endpoint` output, `EMAIL_PORT=587`, `EMAIL_USE_TLS=true`,
   `DEFAULT_FROM_EMAIL` = the approved sender. Set it explicitly: its default is
   `no-reply@<PUBLIC_BASE_URL host>`, and Email Delivery rejects any sender that isn't approved
   (here the site is `listlinkedin.versioncontrol.xyz`, the sender `no-reply@versioncontrol.xyz`).

Always Free allows 3,000 emails a month; Oracle's FAQ lists lower daily caps for free
accounts (about 100–200 a day, 10 a minute). Mail is sent during the request
([deployment](../../docs/deployment.md#email)), so a cap shows up as failed sign-ups.

## Cost

Everything above is inside the Always Free allocation, so it costs nothing as long as the
tenancy stays within it. Oracle may reclaim an *idle* Always Free instance (95th-percentile CPU,
network and memory all under 20% for 7 days) unless the tenancy is upgraded to Pay As You Go,
which keeps Always Free resources free.
