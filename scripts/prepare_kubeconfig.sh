#!/usr/bin/env bash
set -euo pipefail
: "${KUBE_CONFIG_B64:?Configure the KUBE_CONFIG_B64 repository secret first}"
umask 077
configuration="$RUNNER_TEMP/mlops-students.kubeconfig"
printf '%s' "$KUBE_CONFIG_B64" | base64 --decode > "$configuration"
echo "KUBECONFIG=$configuration" >> "$GITHUB_ENV"
