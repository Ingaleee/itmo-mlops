#!/usr/bin/env bash
# Capture only this student's resources, including controller admission failures.
set -euo pipefail
if [[ -z "${KUBECONFIG:-}" || ! -f "$KUBECONFIG" ]]; then exit 0; fi
namespace=${KUBE_NAMESPACE:-mlops-students}
for instance in esolovev-iris esolovev-search-staging esolovev-search-prod; do
  if [[ "$instance" == esolovev-iris ]]; then
    directory=lab1/evidence/diagnostics
    deployment=$instance
  else
    directory="lab2/evidence/$instance/diagnostics"
    deployment="$instance-mlops-search"
  fi
  mkdir -p "$directory"
  kubectl --request-timeout=5s -n "$namespace" get deployment "$deployment" -o json \
    > "$directory/deployment.json" 2> "$directory/errors.log" || true
  for resource in replicasets pods; do
    kubectl --request-timeout=5s -n "$namespace" get "$resource" \
      -l "app.kubernetes.io/instance=$instance" -o json \
      > "$directory/$resource.json" 2>> "$directory/errors.log" || true
  done
done
