#!/usr/bin/env bash
set -euo pipefail
tools="$RUNNER_TEMP/mlops-tools"
mkdir -p "$tools"
curl --fail --silent --show-error --location https://get.helm.sh/helm-v4.3.0-linux-amd64.tar.gz -o "$tools/helm.tar.gz"
curl --fail --silent --show-error --location https://get.helm.sh/helm-v4.3.0-linux-amd64.tar.gz.sha256sum -o "$tools/helm.sha256sum"
(cd "$tools"; sed 's/helm-v4.3.0-linux-amd64.tar.gz/helm.tar.gz/' helm.sha256sum | sha256sum --check)
tar -xzf "$tools/helm.tar.gz" -C "$tools"
mv "$tools/linux-amd64/helm" "$tools/helm"
curl --fail --silent --show-error --location https://dl.k8s.io/release/v1.34.1/bin/linux/amd64/kubectl -o "$tools/kubectl"
curl --fail --silent --show-error --location https://dl.k8s.io/release/v1.34.1/bin/linux/amd64/kubectl.sha256 -o "$tools/kubectl.sha256"
(cd "$tools"; printf '%s  kubectl\n' "$(cat kubectl.sha256)" | sha256sum --check)
chmod +x "$tools/helm" "$tools/kubectl"
echo "$tools" >> "$GITHUB_PATH"
