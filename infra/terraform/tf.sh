#!/usr/bin/env bash
# Run Terraform in Docker (the project keeps no host toolchains). OCI credentials are mounted
# read-only at /root/.oci (where the provider looks) and at the same path, so an absolute
# key_file in ~/.oci/config resolves inside the container.
set -euo pipefail
cd "$(dirname "$0")"
exec docker run --rm -i \
  -v "$PWD":/workspace -w /workspace \
  -v "$HOME/.oci":"$HOME/.oci":ro -v "$HOME/.oci":/root/.oci:ro \
  -e TF_IN_AUTOMATION=1 \
  hashicorp/terraform:1.14 "$@"
