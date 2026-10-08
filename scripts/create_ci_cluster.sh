#!/usr/bin/env bash
set -euo pipefail
tools="$RUNNER_TEMP/mlops-tools"
curl --fail --silent --show-error --location --retry 3 --connect-timeout 10 --max-time 120 https://github.com/k3d-io/k3d/releases/download/v5.9.0/k3d-linux-amd64 -o "$tools/k3d"
curl --fail --silent --show-error --location --retry 3 --connect-timeout 10 --max-time 120 https://github.com/k3d-io/k3d/releases/download/v5.9.0/checksums.txt -o "$tools/k3d-checksums.txt"
(cd "$tools"; awk '$2 == "_dist/k3d-linux-amd64" {print $1 "  k3d"}' k3d-checksums.txt | sha256sum --check)
chmod +x "$tools/k3d"
"$tools/k3d" cluster create ci-labs --servers 1 --agents 0 \
  --image rancher/k3s:v1.35.5-k3s1 --timeout 120s \
  --kubeconfig-update-default=false --kubeconfig-switch-context=false \
  --k3s-arg '--disable=traefik@server:0' --k3s-arg '--disable=metrics-server@server:0'
export KUBECONFIG="$RUNNER_TEMP/local-ci.kubeconfig"
umask 077
"$tools/k3d" kubeconfig get ci-labs > "$KUBECONFIG"
echo "KUBECONFIG=$KUBECONFIG" >> "$GITHUB_ENV"
[[ "$(kubectl config current-context)" == 'k3d-ci-labs' ]]
kubectl create namespace mlops-students
