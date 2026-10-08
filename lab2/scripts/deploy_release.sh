#!/usr/bin/env bash
set -euo pipefail

release=${1:?release required}
environment=${2:?environment required}
ranking_mode=${3:-normal}
: "${IMAGE_REPOSITORY:?image repository required}"
: "${IMAGE_DIGEST:?immutable digest required}"
: "${BUILD_REVISION:?build revision required}"
namespace=${KUBE_NAMESPACE:-mlops-students}
prefix=${RELEASE_PREFIX:-esolovev}
export HELM_DRIVER=configmap
[[ "$release" == "$prefix-search-staging" || "$release" == "$prefix-search-prod" ]] || { echo "Unexpected release name" >&2; exit 2; }
[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "Invalid digest" >&2; exit 2; }
[[ "$ranking_mode" == normal || "$ranking_mode" == reverse ]] || exit 2
evidence="evidence/$release/$ranking_mode"
mkdir -p "$evidence"
previous=0
if helm history "$release" -n "$namespace" -o json > "$evidence/history-before.json" 2>/dev/null; then
  previous=$(python -c 'import json,sys; revisions=[r["revision"] for r in json.load(open(sys.argv[1])) if r["status"]=="deployed"]; print(max(revisions,default=0))' "$evidence/history-before.json")
fi

rollback_release() {
  local failure_stage=$1
  if (( previous == 0 )); then
    echo "No previous successful revision to roll back to" >&2
    return 1
  fi
  helm rollback "$release" "$previous" -n "$namespace" --wait --timeout 3m 2>&1 | tee "$evidence/rollback.log"
  python scripts/verify_release.py --release "$release" --namespace "$namespace" \
    --expected-environment "$environment" --output "$evidence/restored" 2>&1 | tee "$evidence/restored-smoke.log"
  helm history "$release" -n "$namespace" -o json > "$evidence/history-after.json"
  python -c 'import json,sys; json.dump({"failure_stage":sys.argv[1],"restored_revision":int(sys.argv[2]),"rollback_verified":True},open(sys.argv[3],"w"),indent=2)' \
    "$failure_stage" "$previous" "$evidence/rollback.json"
}

if ! helm upgrade --install "$release" helm/mlops-search -n "$namespace" \
  --set-string image.repository="$IMAGE_REPOSITORY" --set-string image.digest="$IMAGE_DIGEST" \
  --set-string buildRevision="$BUILD_REVISION" --set-string environment="$environment" \
  --set-string rankingMode="$ranking_mode" --wait --timeout 3m 2>&1 | tee "$evidence/upgrade.log"; then
  rollback_release deployment_failed
  exit 1
fi
if ! helm test "$release" -n "$namespace" --logs --timeout 2m 2>&1 | tee "$evidence/helm-test.log"; then
  rollback_release helm_test_failed
  exit 1
fi
if ! python scripts/verify_release.py --release "$release" --namespace "$namespace" \
  --expected-digest "$IMAGE_DIGEST" --expected-environment "$environment" \
  --output "$evidence/candidate" 2>&1 | tee "$evidence/candidate-smoke.log"; then
  rollback_release semantic_smoke_failed
  exit 1
fi
helm history "$release" -n "$namespace" -o json > "$evidence/history-after.json"
kubectl -n "$namespace" get deployment "$release-mlops-search" -o json > "$evidence/deployment.json"
