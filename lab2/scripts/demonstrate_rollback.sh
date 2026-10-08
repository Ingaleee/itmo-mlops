#!/usr/bin/env bash
set -euo pipefail
release=${1:?release required}
environment=${2:?environment required}
if bash scripts/deploy_release.sh "$release" "$environment" reverse; then
  echo 'ERROR: reverse ranking passed semantic quality' >&2
  exit 1
fi
python - "$release" "$IMAGE_DIGEST" <<'PY'
import json, sys
from pathlib import Path
directory = Path('evidence') / sys.argv[1] / 'reverse'
result = json.loads((directory / 'rollback.json').read_text())
meta = json.loads((directory / 'candidate/meta.json').read_text())
quality = json.loads((directory / 'candidate/quality.json').read_text())
if not (result['failure_stage'] == 'semantic_smoke_failed' and result['rollback_verified']
        and result['cause']['kind'] == 'semantic_quality' and result['restored_digest'] == sys.argv[2]
        and meta['ranking_mode'] == 'reverse' and meta['image_digest'] == sys.argv[2]
        and (quality['mrr'] < .85 or quality['recall_at_3'] < .90)):
    raise RuntimeError('negative scenario did not prove a quality failure and exact rollback')
print(json.dumps(result))
PY
bash scripts/deploy_release.sh "$release" "$environment" normal
