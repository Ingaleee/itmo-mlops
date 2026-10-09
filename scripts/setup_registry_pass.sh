#!/usr/bin/env bash
set -euo pipefail

[[ "${GITHUB_ACTIONS:-}" == true && -d "${RUNNER_TEMP:-}" ]] || {
  echo 'This setup requires an isolated GitHub Actions runner.' >&2
  exit 1
}
[[ "$(uname -sm)" == 'Linux x86_64' ]] || {
  echo 'The verified credential helper is for Linux amd64.' >&2
  exit 1
}

sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends pass gnupg

auth_root="$(mktemp -d "$RUNNER_TEMP/itmo-registry-auth.XXXXXX")"
chmod 700 "$auth_root"
touch "$auth_root/.itmo-registry-auth"
export COURSE_REGISTRY_AUTH_ROOT="$auth_root"
export GNUPGHOME="$auth_root/gnupg"
export PASSWORD_STORE_DIR="$auth_root/password-store"
export DOCKER_CONFIG="$auth_root/docker"
mkdir -m 700 "$GNUPGHOME" "$PASSWORD_STORE_DIR" "$DOCKER_CONFIG" "$auth_root/bin"

# Record cleanup paths before downloading tools or generating the temporary key.
for variable in COURSE_REGISTRY_AUTH_ROOT GNUPGHOME PASSWORD_STORE_DIR DOCKER_CONFIG; do
  printf '%s=%s\n' "$variable" "${!variable}" >> "$GITHUB_ENV"
done
printf '%s\n' "$auth_root/bin" >> "$GITHUB_PATH"

helper="$auth_root/bin/docker-credential-pass"
curl --fail --silent --show-error --location --retry 3 --connect-timeout 10 --max-time 120 \
  'https://github.com/docker/docker-credential-helpers/releases/download/v0.9.8/docker-credential-pass-v0.9.8.linux-amd64' \
  --output "$helper"
printf '3ae93407d42dc90bd0393b0a50da3ce95246d3f30c3255225cb6b0401cd74cac  %s\n' "$helper" | sha256sum --check --status
chmod 700 "$helper"

# This key belongs only to this disposable runner and is removed after logout.
gpg --batch --pinentry-mode loopback --passphrase '' --quick-generate-key \
  'ITMO temporary registry credentials <esolovev@users.noreply.github.com>' default default 1d
fingerprint="$(gpg --batch --list-secret-keys --with-colons 2>/dev/null | awk -F: '$1 == "fpr" {print $10; exit}')"
[[ "$fingerprint" =~ ^[0-9A-F]{40}$ ]] || { echo 'GPG key generation failed.' >&2; exit 1; }
pass init "$fingerprint"
printf '{"credsStore":"pass"}\n' > "$DOCKER_CONFIG/config.json"
echo 'Isolated GPG/pass credential store initialized; helper checksum verified.'
