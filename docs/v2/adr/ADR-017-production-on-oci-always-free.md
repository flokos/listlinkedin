# ADR-017: Production on Oracle Cloud Always Free, managed with Terraform

- Status: Accepted (2026-11-01, the user approved the plan; provisioned the same day)
- Changes: where [deployment](../../deployment.md) runs. Related: D32
  ([20](../20-DECISIONS-AND-OPEN-QUESTIONS.md)), [14](../14-INFRASTRUCTURE.md)

## Context

V2 was released on GitHub without a server (D32). The deployment guide describes one Linux
host with rootful Docker and Compose, ports 80 and 443, a DNS name and an SMTP relay, and says
2 vCPUs with 2–4 GB serves a team. The user chose Oracle Cloud Infrastructure in
`eu-frankfurt-1`, using an existing `ListLinkedIn` compartment and a deployer account limited to
compute, networking, storage and Email Delivery in it.

## Decision

- **One Ampere A1 VM** (`VM.Standard.A1.Flex`, 2 OCPU, 12 GB, Ubuntu 24.04 arm64, 50 GB boot
  volume): the whole Always Free A1 allowance. The stack runs unchanged under
  `compose.prod.yaml`; all its images are multi-arch.
- **A 50 GB block volume** holds Docker's data root and local backups, so the database survives
  rebuilding the instance. A **reserved public IPv4** keeps DNS stable across rebuilds.
- **Network:** one VCN and public subnet. Only 80 and 443 are open to everyone; SSH only from
  listed administrator addresses. No load balancer: nginx on the host terminates TLS, as before.
- **Email:** OCI Email Delivery as the SMTP relay (domain with DKIM, one approved sender).
- **Terraform** in `infra/terraform/`, run through the `hashicorp/terraform` image like every
  other tool here. Validations keep a plan inside the Always Free limits.

## Consequences

- Nothing new joins the application stack; [14](../14-INFRASTRUCTURE.md) is unchanged in kind.
- Always Free A1 capacity can be unavailable, and Oracle may reclaim idle Always Free
  instances. Upgrading the tenancy to Pay As You Go removes the reclamation risk at no cost
  inside the limits.
- Free-tier email caps (3,000/month, lower daily caps) bound sign-up volume until raised.
- Terraform state stays local until the deployer group can manage Object Storage.
- Arm64 is now the production architecture; CI builds and tests on amd64.
