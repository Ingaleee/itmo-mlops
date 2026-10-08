import argparse
import json
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path


def get_json(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as response:
        return json.load(response)


def verify(base, output, expected_digest=None, expected_environment=None):
    output.mkdir(parents=True, exist_ok=True)
    for _ in range(40):
        try:
            ready = get_json(base, "/readyz")
            break
        except Exception:
            time.sleep(.5)
    else:
        raise RuntimeError("service did not become ready")
    meta = get_json(base, "/meta")
    (output / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    request_id = "acceptance-" + uuid.uuid4().hex
    request = urllib.request.Request(
        base + "/v1/search",
        data=json.dumps({"query": "как вернуть предыдущую модель после плохого релиза", "limit": 3}).encode(),
        headers={"Content-Type": "application/json", "X-Request-ID": request_id},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.load(response)
        response_request_id = response.headers["X-Request-ID"]
    report = {"ready": ready, "meta": meta, "search": result}
    (output / "smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert result["results"][0]["id"] == "doc-rollback", result
    assert result["request_id"] == request_id == response_request_id
    assert meta["ranking_mode"] == "normal", meta
    assert ready["index_version"] == meta["index_version"] == result["index_version"]
    if expected_digest:
        assert meta["image_digest"] == expected_digest, meta
    if expected_environment:
        assert meta["environment"] == expected_environment, meta
    print(json.dumps(report, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release")
    parser.add_argument("--base-url")
    parser.add_argument("--namespace", default="mlops-students")
    parser.add_argument("--port", type=int, default=18090)
    parser.add_argument("--output", type=Path, default=Path("evidence/smoke"))
    parser.add_argument("--expected-digest")
    parser.add_argument("--expected-environment")
    args = parser.parse_args()
    if not args.base_url and not args.release:
        parser.error("provide --base-url or --release")
    process = None
    try:
        if args.release:
            process = subprocess.Popen([
                "kubectl", "-n", args.namespace, "port-forward", f"service/{args.release}-mlops-search", f"{args.port}:80"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        verify(args.base_url.rstrip("/") if args.base_url else f"http://127.0.0.1:{args.port}", args.output,
               args.expected_digest, args.expected_environment)
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
