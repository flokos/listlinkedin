# ADR-022: SSH to the production host from any address, with the key as the only way in

- Status: Accepted (2026-11-11, user: D38). Changes the SSH part of
  [ADR-017](ADR-017-production-on-oci-always-free.md) ("SSH only from listed administrator
  addresses"). Leaves [ADR-018](ADR-018-pull-based-deployment.md) as it is.
- Related: [infra/terraform/README.md](../../../infra/terraform/README.md),
  [docs/deployment.md](../../deployment.md)

## Context

ADR-017 opened port 22 only to the addresses in `admin_cidrs`: one, the owner's. That address
belongs to a home connection and changes. On 2026-11-11 it had changed on the day `v2.3.0`
was released, and the owner could not look at the deployment on the server until the rule
was changed with Terraform. The deployer account can't run commands on the instance through
OCI, by design.

The owner chose (D38) to stop tying SSH to an address and to rely on the key.

## Decision

1. **`admin_cidrs` may be `["0.0.0.0/0"]`,** and that is what the example and production
   use: the instance's security group accepts TCP 22 from any address. The variable stays,
   so an installation with fixed addresses can still list them.
2. **sshd accepts the key and nothing else.** `host/bootstrap.sh` writes
   `/etc/ssh/sshd_config.d/00-listlinkedin-key-only.conf`: no password or
   keyboard-interactive authentication, no root login, `AuthenticationMethods publickey`.
   Ubuntu's cloud image already refuses passwords; this makes it this project's own setting,
   which an image or package update doesn't change. On the running server the file is
   installed by hand once (the README says how), since cloud-init runs only at first boot.
3. **The key stays with the owner.** It is not stored in GitHub or any other service, and
   nothing outside logs in to the server: deployments are still pulled by the server
   (ADR-018).

## Consequences

- The owner can reach the server from wherever they are, without a Terraform change first.
- Port 22 is visible to the whole internet and will be probed continuously. What protects
  it is the key (ed25519, on the owner's machine) and sshd itself: a flaw in sshd that works
  before authentication is now reachable by anyone, where before it was reachable from one
  address. `unattended-upgrades` installs security updates; that matters more now.
- The auth log fills with failed attempts. No rate limiting is added (fail2ban or the like):
  with keys only there is nothing to guess. It can be added if the noise or load matters.
- Losing the private key, or leaking it, is now the whole risk: replace `ssh_public_key`
  and `~ubuntu/.ssh/authorized_keys` at once if that happens.
- To go back: list addresses in `admin_cidrs` and apply.

## Considered and not chosen

- **Keep the address list and update it when the address changes** (a script around the
  same Terraform rule): keeps the smaller exposure, but the owner must be at a machine with
  the OCI credentials to get in, which is what failed.
- **A GitHub workflow that logs in with the server's key:** rejected in ADR-018 already; it
  would put a key to production in an outside service.
- **OCI Bastion or the instance agent's run-command:** more moving parts and more
  permissions for the deployer account.
