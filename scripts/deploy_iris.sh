#!/usr/bin/env bash
set -euo pipefail
: "${IRIS_IMAGE:?image repository required}"
: "${IRIS_DIGEST:?digest required}"
[[ "$IRIS_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
python - <<'PY'
import os
from pathlib import Path
text = Path('lab1/k8s/app.yaml').read_text()
placeholder = 'ghcr.io/ingaleee/esolovev-iris:v1'
if text.count(placeholder) != 1 or os.environ['IRIS_IMAGE'] != 'ghcr.io/ingaleee/esolovev-iris':
    raise RuntimeError('unexpected Iris manifest or repository')
text = text.replace(placeholder, os.environ['IRIS_IMAGE'] + '@' + os.environ['IRIS_DIGEST'])
Path(os.environ['RUNNER_TEMP'], 'iris.yaml').write_text(text)
PY
kubectl apply --dry-run=server -f "$RUNNER_TEMP/iris.yaml"
kubectl apply -f "$RUNNER_TEMP/iris.yaml"
kubectl -n mlops-students rollout status deployment/esolovev-iris --timeout=180s
mkdir -p lab1/evidence
kubectl -n mlops-students get deployment esolovev-iris -o json > lab1/evidence/deployment.json
python - <<'PY'
import json, os
from pathlib import Path
resource = json.loads(Path('lab1/evidence/deployment.json').read_text())
expected = os.environ['IRIS_IMAGE'] + '@' + os.environ['IRIS_DIGEST']
if resource['spec']['template']['spec']['containers'][0]['image'] != expected:
    raise RuntimeError('Iris Deployment digest mismatch')
PY
port=$(python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
kubectl -n mlops-students port-forward --address=127.0.0.1 service/esolovev-iris "$port:80" > lab1/evidence/port-forward.log 2>&1 &
forward_pid=$!
trap 'kill "$forward_pid" 2>/dev/null || true' EXIT
for attempt in {1..30}; do
  kill -0 "$forward_pid" 2>/dev/null || { echo 'Iris port-forward exited; see evidence/port-forward.log' >&2; exit 1; }
  if curl --fail --silent --max-time 2 "http://127.0.0.1:$port/health" > /dev/null; then break; fi
  sleep 1
done
python lab1/scripts/check_api.py --base-url "http://127.0.0.1:$port" --output lab1/evidence/cluster-api.json
