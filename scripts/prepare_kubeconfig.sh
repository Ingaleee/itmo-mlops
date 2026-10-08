#!/usr/bin/env bash
set -euo pipefail
: "${KUBE_CONFIG_B64:?Configure the KUBE_CONFIG_B64 repository secret first}"
umask 077
configuration="$RUNNER_TEMP/mlops-students.kubeconfig"
printf '%s' "$KUBE_CONFIG_B64" | base64 --decode > "$configuration"
kubectl config view --kubeconfig "$configuration" --raw -o json > "$RUNNER_TEMP/kubeconfig-validation.json"
python - "$RUNNER_TEMP/kubeconfig-validation.json" <<'PY'
import json, sys
configuration = json.load(open(sys.argv[1]))
for entry in configuration.get('users', []):
    user = entry['user']
    if 'exec' in user or 'auth-provider' in user:
        raise RuntimeError('teaching kubeconfig must use static credentials, not executable credential helpers')
for entry in configuration.get('clusters', []):
    cluster = entry['cluster']
    if cluster.get('insecure-skip-tls-verify') or not cluster.get('server', '').startswith('https://'):
        raise RuntimeError('teaching kubeconfig must verify TLS over HTTPS')
PY
rm -f "$RUNNER_TEMP/kubeconfig-validation.json"
echo "KUBECONFIG=$configuration" >> "$GITHUB_ENV"
