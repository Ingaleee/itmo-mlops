"""Run the existing CPU acceptance on the teaching cluster, restoring labs 1/2."""
import hashlib
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zlib


ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'lab3'
OUT = ROOT / 'lab3/evidence/teaching'
OUT.mkdir(parents=True, exist_ok=True)
CONFIG = os.environ['KUBECONFIG']
K = ['kubectl', '--kubeconfig', CONFIG, '--request-timeout=20s', '-n', 'itmo-student-01']
APP_DIGEST = 'sha256:35798606e7d00d5818b56c7e0a1e42902cece411533155fff3ad16f41daf7943'
CPU_DIGEST = 'sha256:01cbe54ced5ed14fb5c0677155100f808e093518f5a726c8b1157553f32409e4'
APP = 'docker.io/inga1e/esolovev-knowledge@' + APP_DIGEST
CPU = 'docker.io/inga1e/esolovev-ollama-cpu@' + CPU_DIGEST
WEIGHTS = '/models/blobs/sha256-3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
OLD = ['esolovev-iris', 'esolovev-search-staging-mlops-search', 'esolovev-search-prod-mlops-search']
NEW = ['kb-mcp', 'knowledge-portal', 'llm-local']
env = os.environ.copy()
env['PYTHONUTF8'] = '1'
restore = {}


def run(args, *, cwd=ROOT, timeout=90, output=None, task_env=env):
    if output:
        with (OUT / output).open('w', encoding='utf-8') as stream:
            return subprocess.run(args, cwd=cwd, env=task_env, check=True, timeout=timeout,
                                  stdout=stream, stderr=subprocess.STDOUT)
    return subprocess.run(args, cwd=cwd, env=task_env, check=True, timeout=timeout)


def capture(name, args, timeout=50):
    return run(K + args, output=name, timeout=timeout)


def read_resource(kind, *names):
    return json.loads(subprocess.check_output(K + ['get', kind, *names, '-o', 'json'], timeout=40))


def verify_mirrors():
    for name, digest in [('knowledge', APP_DIGEST), ('ollama-cpu', CPU_DIGEST)]:
        for registry in ['ghcr.io/ingaleee', 'docker.io/inga1e']:
            image = registry + '/esolovev-' + name + '@' + digest
            raw = subprocess.check_output(['docker', 'buildx', 'imagetools', 'inspect', '--raw', image], timeout=60)
            assert 'sha256:' + hashlib.sha256(raw).hexdigest() == digest, 'OCI mirror mismatch'
    (OUT / 'mirrors.json').write_text(json.dumps({'status': 'passed', 'app': APP, 'ollama': CPU,
                                                 'manifests_identical': True}, indent=2) + '\n')
    print('Both lab 3 mirrors match the exact published CI release', flush=True)


def probe_inside_cluster():
    # Keep the application's two-second MCP contract on its actual in-cluster
    # boundary. The workstation's multi-roundtrip tunnel is a different path.
    payload = {'script': (LAB / 'scripts/probe_mcp.py').read_text(encoding='utf-8'),
               'controls': (LAB / 'control-questions.json').read_text(encoding='utf-8')}
    runner = '''import json,os,sys
from pathlib import Path
payload=json.load(sys.stdin)
directory=Path('/tmp/teaching-acceptance')
directory.mkdir(exist_ok=True)
os.chdir(directory)
Path('control-questions.json').write_text(payload['controls'],encoding='utf-8')
exec(compile(payload['script'],'/app/scripts/probe_mcp.py','exec'),{'__name__':'__main__','__file__':'/app/scripts/probe_mcp.py'})
print('MCP_ACCEPTANCE_REPORT='+Path('evidence/mcp.json').read_text(encoding='utf-8'))
'''
    raw = subprocess.check_output(K + ['exec', '-i', 'deployment/knowledge-portal', '--', 'python', '-c', runner],
                                  input=json.dumps(payload).encode('utf-8'), timeout=150)
    report = json.loads(raw.decode('utf-8').rsplit('MCP_ACCEPTANCE_REPORT=', 1)[1])
    assert report['status'] == 'passed' and len(report['controls']) == 8
    (OUT / 'mcp.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Independent real MCP client passed all controls inside the teaching cluster', flush=True)


def verify_inside_cluster(after_restart=False):
    """Keep long-running HTTP verification alive when the operator tunnel drops."""
    payload = {'files': {name: (LAB / 'scripts' / name).read_text(encoding='utf-8')
                         for name in ['verify_portal.py', 'verify_runtime.py']},
               'controls': (LAB / 'control-questions.json').read_text(encoding='utf-8'),
               'privacy': (ROOT / 'docs/media/sources/knowledge-privacy.json').read_text(encoding='utf-8'),
               'after_restart': after_restart}
    launcher = '''import json,os,subprocess,sys
from pathlib import Path
p=json.load(sys.stdin)
d=Path('/tmp/teaching-acceptance')
(d/'scripts').mkdir(parents=True,exist_ok=True)
(d/'evidence').mkdir(exist_ok=True)
if not (d/'model').exists(): (d/'model').symlink_to('/app/model',target_is_directory=True)
for name,source in p['files'].items(): (d/'scripts'/name).write_text(source,encoding='utf-8')
(d/'control-questions.json').write_text(p['controls'],encoding='utf-8')
(d/'evidence/privacy.json').write_text(p['privacy'],encoding='utf-8')
token=d/'portal.token'
token.write_text(os.environ['PORTAL_ACCESS_TOKEN'],encoding='utf-8')
token.chmod(0o600)
commands=[[sys.executable,str(d/'scripts/verify_portal.py'),'--base-url','http://127.0.0.1:8000','--route','local','--portal-token-file',str(token),'--output',str(d/('after-restart.json' if p['after_restart'] else 'control-answers.json'))]]
if p['after_restart']: commands[0]+=['--cases','K01']
else: commands.append([sys.executable,str(d/'scripts/verify_runtime.py'),'--base-url','http://127.0.0.1:8000','--portal-token-file',str(token),'--output',str(d/'queue-and-filter.json')])
(d/'commands.json').write_text(json.dumps(commands))
worker=d/'worker.py'
worker.write_text(''' + '"""' + '''import json,subprocess,sys
from pathlib import Path
d=Path(__file__).parent
result={'status':'failed'}
try:
 for command in json.loads((d/'commands.json').read_text()):
  subprocess.run(command,check=True,timeout=1100)
 result={'status':'passed'}
finally:
 (d/'portal.token').unlink(missing_ok=True)
 (d/'runner-result.json').write_text(json.dumps(result))
''' + '"""' + ''',encoding='utf-8')
(d/'runner-result.json').unlink(missing_ok=True)
env=os.environ.copy();env['PYTHONPATH']='/app';env['PYTHONUNBUFFERED']='1'
with (d/'worker.log').open('w') as log:
 child=subprocess.Popen([sys.executable,str(worker)],cwd=d,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
print(json.dumps({'pid':child.pid,'started':True}))
'''
    subprocess.run(K + ['exec', '-i', 'deployment/knowledge-portal', '--', 'python', '-c', launcher],
                   input=json.dumps(payload).encode('utf-8'), check=True, timeout=60)
    probe = '''import json
from pathlib import Path
d=Path('/tmp/teaching-acceptance')
result=json.loads((d/'runner-result.json').read_text()) if (d/'runner-result.json').exists() else {'status':'running'}
result['tail']=(d/'worker.log').read_text()[-1400:]
print(json.dumps(result))
'''
    previous = ''
    for _ in range(100):
        try:
            state = json.loads(subprocess.check_output(K + ['exec', 'deployment/knowledge-portal', '--', 'python', '-c', probe], timeout=35))
        except (subprocess.SubprocessError, json.JSONDecodeError):
            time.sleep(10)
            continue
        if state['tail'] != previous:
            print(state['tail'], flush=True)
            previous = state['tail']
        if state['status'] != 'running':
            break
        time.sleep(10)
    else:
        raise RuntimeError('In-cluster acceptance exceeded bounded wait')
    for name in (['after-restart.json'] if after_restart else ['control-answers.json', 'queue-and-filter.json']):
        remote = "import base64,zlib;from pathlib import Path;print(base64.b64encode(zlib.compress(Path('/tmp/teaching-acceptance/" + name + "').read_bytes())).decode())"
        raw = subprocess.check_output(K + ['exec', 'deployment/knowledge-portal', '--', 'python', '-c', remote], timeout=60)
        (OUT / name).write_bytes(zlib.decompress(base64.b64decode(raw)))
    assert state['status'] == 'passed', 'In-cluster CPU verifier failed; see captured reports'


def stop_new():
    for name in NEW:
        run(K + ['scale', 'deployment/' + name, '--replicas=0'], timeout=40)
    for name in NEW:
        run(K + ['rollout', 'status', 'deployment/' + name, '--timeout=60s'], timeout=75)


def restore_labs(original):
    stop_new()
    replicas = {item['metadata']['name']: item['spec']['replicas'] for item in original['items']}
    assert set(replicas) == set(OLD)
    for name, count in replicas.items():
        run(K + ['scale', 'deployment/' + name, '--replicas=' + str(count)], timeout=40)
    for name in OLD:
        run(K + ['rollout', 'status', 'deployment/' + name, '--timeout=3m'], timeout=200)
    final = read_resource('deployments', *OLD)
    for resource in final['items']:
        name = resource['metadata']['name']
        before = next(r for r in original['items'] if r['metadata']['name'] == name)
        assert resource['spec']['replicas'] == resource['status'].get('readyReplicas') == replicas[name]
        assert resource['spec']['template'] == before['spec']['template']
    (OUT / 'previous-labs-restored.json').write_text(json.dumps(
        {'status': 'passed', 'replicas': replicas, 'pod_templates_unchanged': True}, indent=2) + '\n')
    print('Own labs 1/2 restored; Helm releases and PVC preserved', flush=True)


if '--restore-only' in sys.argv:
    if (OUT / 'previous-labs.json').exists() and not (OUT / 'previous-labs-restored.json').exists():
        restore_labs(json.loads((OUT / 'previous-labs.json').read_text()))
    raise SystemExit(0)


verify_mirrors()
original = read_resource('deployments', *OLD)
for resource in original['items']:
    assert resource['metadata']['name'] in OLD
    assert resource['spec']['replicas'] == resource['status'].get('readyReplicas') == 1
    restore[resource['metadata']['name']] = resource['spec']['replicas']
(OUT / 'previous-labs.json').write_text(json.dumps(original, indent=2) + '\n')
changed = False
try:
    changed = True
    print('Temporarily stopping only own labs 1/2 replicas for the 4G CPU profile', flush=True)
    for name in OLD:
        run(K + ['scale', 'deployment/' + name, '--replicas=0'], timeout=40)
    for name in OLD:
        run(K + ['rollout', 'status', 'deployment/' + name, '--timeout=60s'], timeout=75)
    run([sys.executable, 'lab3/scripts/deploy.py', '--kubeconfig', CONFIG,
         '--app-image', APP, '--ollama-image', CPU, '--apply'], timeout=1100)
    print('All three teaching lab 3 deployments rolled out', flush=True)
    capture('pods-before.json', ['get', 'pods', '-l', 'app.kubernetes.io/part-of=esolovev-knowledge', '-o', 'json'])
    capture('pvc.json', ['get', 'pvc', 'knowledge-models', '-o', 'json'])
    capture('quota.json', ['get', 'quota', 'student-budget', '-o', 'json'])
    metric = ['exec', 'deployment/llm-local', '--', 'sh', '-c',
              'cat /sys/fs/cgroup/memory.current /sys/fs/cgroup/memory.peak /sys/fs/cgroup/memory.events /sys/fs/cgroup/cpu.stat']
    capture('resources-before.txt', metric)
    capture('ollama-ps.txt', ['exec', 'deployment/llm-local', '--', 'ollama', 'ps'])
    capture('weights-before.txt', ['exec', 'deployment/llm-local', '--', 'sha256sum', WEIGHTS], timeout=100)
    probe_inside_cluster()
    privacy = json.loads((ROOT / 'docs/media/sources/knowledge-privacy.json').read_text(encoding='utf-8'))
    assert privacy['status'] == 'passed' and privacy['external_requests'] == 0 and privacy['closed_quote_excluded']
    (OUT / 'privacy.json').write_text(json.dumps(privacy, indent=2) + '\n', encoding='utf-8')
    verify_inside_cluster()
    capture('resources-after-generation.txt', metric)
    before = read_resource('pods', '-l', 'app=llm-local')['items']
    assert len(before) == 1
    old_uid = before[0]['metadata']['uid']
    print('CPU controls and cancellation passed; checking persistence across Pod recreation', flush=True)
    run(K + ['delete', 'pod', before[0]['metadata']['name'], '--wait=true'], timeout=100)
    run(K + ['rollout', 'status', 'deployment/llm-local', '--timeout=8m'], timeout=500)
    capture('pods-after-restart.json', ['get', 'pods', '-l', 'app.kubernetes.io/part-of=esolovev-knowledge', '-o', 'json'])
    after = read_resource('pods', '-l', 'app=llm-local')['items']
    assert len(after) == 1 and after[0]['metadata']['uid'] != old_uid
    verify_inside_cluster(after_restart=True)
    capture('weights-after.txt', ['exec', 'deployment/llm-local', '--', 'sha256sum', WEIGHTS], timeout=100)
    assert (OUT / 'weights-before.txt').read_bytes() == (OUT / 'weights-after.txt').read_bytes()
    capture('resources-after-restart.txt', metric)
    report = {'status': 'passed', 'environment': 'personal teaching Kubernetes',
              'app': APP, 'ollama': CPU, 'revision': '2e9c53965dbf2685100f7dc2da5f9e68120bb050',
              'cpu_control_answers': 8, 'mcp': 'passed', 'privacy': 'passed', 'queue_and_cancellation': 'passed',
              'pod_uid_before': old_uid, 'pod_uid_after': after[0]['metadata']['uid'], 'weights_unchanged': True,
              'cloud': 'not configured; separate egress and credential boundary'}
    (OUT / 'acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
    print('TEACHING_LAB3_CPU_ACCEPTANCE_PASSED', flush=True)
except Exception as error:
    (OUT / 'failure.json').write_text(json.dumps({'type': type(error).__name__, 'message': str(error)}, indent=2) + '\n')
    try:
        capture('pods-on-failure.json', ['get', 'pods', '-l', 'app.kubernetes.io/part-of=esolovev-knowledge', '-o', 'json'])
    except Exception:
        pass
    raise
finally:
    if changed:
        restore_labs(original)
