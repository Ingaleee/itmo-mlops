#!/usr/bin/env bash
set -euo pipefail
: "${IRIS_IMAGE:?image repository required}"
: "${IRIS_DIGEST:?digest required}"
[[ "$IRIS_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
python - <<'PY'
import os
from pathlib import Path
text = Path('lab1/k8s/app.yaml').read_text()
text = text.replace('ghcr.io/ingaleee/esolovev-iris:v1', os.environ['IRIS_IMAGE'] + '@' + os.environ['IRIS_DIGEST'])
Path(os.environ['RUNNER_TEMP'], 'iris.yaml').write_text(text)
PY
kubectl apply --dry-run=server -f "$RUNNER_TEMP/iris.yaml"
kubectl apply -f "$RUNNER_TEMP/iris.yaml"
kubectl -n mlops-students rollout status deployment/esolovev-iris --timeout=180s
mkdir -p lab1/evidence
kubectl -n mlops-students get deployment esolovev-iris -o json > lab1/evidence/deployment.json
kubectl -n mlops-students port-forward service/esolovev-iris 18092:80 > "$RUNNER_TEMP/iris-forward.log" 2>&1 &
forward_pid=$!
trap 'kill "$forward_pid" 2>/dev/null || true' EXIT
for attempt in {1..30}; do
  if curl --fail --silent http://127.0.0.1:18092/health > /dev/null; then break; fi
  sleep 1
done
python lab1/scripts/check_api.py --base-url http://127.0.0.1:18092 --output lab1/evidence/cluster-api.json
