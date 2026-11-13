#!/usr/bin/env bash
set -euo pipefail
: "${APP_IMAGE:?immutable app image required}"
: "${OLLAMA_IMAGE:?immutable Ollama image required}"
: "${KUBECONFIG:?isolated CI kubeconfig required}"
namespace=itmo-student-01
mkdir -p lab3/evidence/kubernetes
kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$namespace" create quota student-budget --hard='requests.cpu=2600m,limits.cpu=2600m,requests.memory=4G,limits.memory=4G,services.loadbalancers=0,services.nodeports=0' --dry-run=client -o yaml | kubectl apply -f -
python - <<'PY'
import os,secrets
from pathlib import Path
for name in ('mcp','portal'):
    token=secrets.token_hex(32)
    print('::add-mask::'+token)
    Path(os.environ['RUNNER_TEMP'],name+'.token').write_text(token)
PY
python - <<'PY' | kubectl -n "$namespace" apply --server-side --field-manager=knowledge-ci -f -
import base64,json,os
auth=base64.b64encode((os.environ['GITHUB_ACTOR']+':'+os.environ['GH_PACKAGES_TOKEN']).encode()).decode()
config=json.dumps({'auths':{'ghcr.io':{'auth':auth}}}).encode()
print(json.dumps({'apiVersion':'v1','kind':'Secret','metadata':{'name':'ci-registry'},
  'type':'kubernetes.io/dockerconfigjson','data':{'.dockerconfigjson':base64.b64encode(config).decode()}}))
PY
python lab3/scripts/prepare_secrets.py --kubeconfig "$KUBECONFIG" \
  --corpus lab3/testing/public-corpus.json --mcp-token "$RUNNER_TEMP/mcp.token" --portal-token "$RUNNER_TEMP/portal.token"
python lab3/scripts/deploy.py --kubeconfig "$KUBECONFIG" --app-image "$APP_IMAGE" --ollama-image "$OLLAMA_IMAGE" --image-pull-secret ci-registry --apply
kubectl -n "$namespace" get pods -o json > lab3/evidence/kubernetes/pods-before.json
kubectl -n "$namespace" get pvc -o json > lab3/evidence/kubernetes/pvc.json
kubectl -n "$namespace" get resourcequota student-budget -o json > lab3/evidence/kubernetes/quota.json
kubectl -n "$namespace" exec deployment/llm-local -- ollama ps > lab3/evidence/kubernetes/ollama-ps.txt
kubectl -n "$namespace" exec deployment/llm-local -- sh -c 'cat /sys/fs/cgroup/memory.current /sys/fs/cgroup/memory.peak /sys/fs/cgroup/memory.events /sys/fs/cgroup/cpu.stat' > lab3/evidence/kubernetes/resources-before.txt
kubectl -n "$namespace" port-forward --address=127.0.0.1 service/knowledge-portal 18081:8000 > lab3/evidence/kubernetes/portal-forward.log 2>&1 &
portal_pid=$!
kubectl -n "$namespace" port-forward --address=127.0.0.1 service/kb-mcp 18080:8000 > lab3/evidence/kubernetes/mcp-forward.log 2>&1 &
mcp_pid=$!
trap 'kill "$portal_pid" "$mcp_pid" 2>/dev/null || true; rm -f "$RUNNER_TEMP/mcp.token" "$RUNNER_TEMP/portal.token"' EXIT
for attempt in {1..30}; do
  kill -0 "$portal_pid" && kill -0 "$mcp_pid"
  if curl --fail --silent --max-time 3 http://127.0.0.1:18081/readyz > /dev/null; then break; fi
  sleep 1
done
export MCP_URL=http://127.0.0.1:18080/mcp
MCP_SERVICE_TOKEN=$(cat "$RUNNER_TEMP/mcp.token")
export MCP_SERVICE_TOKEN
(
  cd lab3
  python scripts/probe_mcp.py
  python scripts/check_privacy.py testing/public-corpus.json
  python scripts/verify_portal.py --route local --portal-token-file "$RUNNER_TEMP/portal.token" --output evidence/kubernetes/control-answers.json
)
kubectl -n "$namespace" exec deployment/llm-local -- sh -c 'cat /sys/fs/cgroup/memory.current /sys/fs/cgroup/memory.peak /sys/fs/cgroup/memory.events /sys/fs/cgroup/cpu.stat' > lab3/evidence/kubernetes/resources-after-generation.txt
kubectl -n "$namespace" delete pod -l app=llm-local --wait=true
kubectl -n "$namespace" rollout status deployment/llm-local --timeout=5m
kubectl -n "$namespace" get pods -o json > lab3/evidence/kubernetes/pods-after-restart.json
(
  cd lab3
  python scripts/verify_portal.py --route local --cases K01 --portal-token-file "$RUNNER_TEMP/portal.token" --output evidence/kubernetes/after-restart.json
)
kubectl -n "$namespace" exec deployment/llm-local -- ollama ps > lab3/evidence/kubernetes/ollama-ps-after.txt
