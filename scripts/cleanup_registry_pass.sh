#!/usr/bin/env bash
set -euo pipefail

[[ -n "${COURSE_REGISTRY_AUTH_ROOT:-}" ]] || exit 0
root="$(realpath "$COURSE_REGISTRY_AUTH_ROOT")"
runner_root="$(realpath "$RUNNER_TEMP")"
[[ "$(dirname "$root")" == "$runner_root" && "$(basename "$root")" == itmo-registry-auth.* && -f "$root/.itmo-registry-auth" ]] || {
  echo 'Refusing cleanup outside the marked temporary credential store.' >&2
  exit 1
}
[[ "${DOCKER_CONFIG:-}" == "$root/docker" && "${GNUPGHOME:-}" == "$root/gnupg" ]] || {
  echo 'Unexpected credential directories.' >&2
  exit 1
}

docker logout ghcr.io >/dev/null 2>&1 || true
gpgconf --homedir "$GNUPGHOME" --kill all || true
rm -rf -- "$root"
[[ ! -e "$root" ]] || { echo 'Temporary credentials were not removed.' >&2; exit 1; }
mkdir -p lab1/evidence/registry-credentials
printf '{"status":"passed","temporary_credentials_removed":true}\n' > lab1/evidence/registry-credentials/cleanup.json
echo 'Temporary registry credentials and GPG key removed.'
