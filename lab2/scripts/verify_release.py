"""Check the actual API and deployed image, preserving evidence before failure."""
import argparse
import json
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.evaluation import summarize


class VerificationError(RuntimeError):
    def __init__(self, message, kind="contract"):
        super().__init__(message)
        self.kind = kind


def require(condition, message, kind="contract"):
    if not condition:
        raise VerificationError(message, kind)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_json(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as response:
        return json.load(response)


def verify(base, output, expected_digest=None, expected_environment=None, expected_revision=None,
           expected_index=None, forward=None):
    for _ in range(40):
        if forward is not None and forward.poll() is not None:
            raise VerificationError("port-forward exited; see port-forward.log", "transport")
        try:
            ready = get_json(base, "/readyz")
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(.5)
    else:
        raise VerificationError("service did not become ready", "transport")
    meta = get_json(base, "/meta")
    save(output / "meta.json", meta)
    require(ready.get("status") == "ready", "readiness contract failed")
    require(get_json(base, "/livez")["status"] == "ok", "liveness contract failed")
    require(ready["index_version"] == meta["index_version"], "readiness and metadata disagree")
    require(re.fullmatch(r"[0-9a-f]{64}", meta.get("artifact_sha256", "")), "artifact fingerprint missing")
    for actual, expected, label in ((meta["image_digest"], expected_digest, "image digest"),
                                    (meta["environment"], expected_environment, "environment"),
                                    (meta["build_revision"], expected_revision, "build revision"),
                                    (meta["index_version"], expected_index, "index version")):
        if expected:
            require(actual == expected, f"unexpected {label}: {actual}")

    cases = json.loads(Path(__file__).resolve().parents[1].joinpath("data/eval.json").read_text(encoding="utf-8"))
    results = []
    for case in cases:
        request_id = "acceptance-" + uuid.uuid4().hex
        request = urllib.request.Request(base + "/v1/search",
            data=json.dumps({"query": case["query"], "limit": 3}).encode(),
            headers={"Content-Type": "application/json", "X-Request-ID": request_id})
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.load(response)
            echoed_id = response.headers["X-Request-ID"]
        results.append(result)
        require(result["request_id"] == request_id == echoed_id, "request ID propagation failed")
        require(result["index_version"] == meta["index_version"], "search and metadata disagree")
        require(0 < len(result["results"]) <= 3, "invalid result count")
        require(all(0 <= item["score"] <= 1 for item in result["results"]), "score is not cosine similarity")
    report = {"ready": ready, "meta": meta, "searches": results}
    save(output / "smoke.json", report)
    quality = summarize(cases, [[item["id"] for item in result["results"]] for result in results])
    save(output / "quality.json", quality)
    require(quality["mrr"] >= .85 and quality["recall_at_3"] >= .90 and meta["ranking_mode"] == "normal",
            f"release failed semantic quality: MRR={quality['mrr']}, hit rate={quality['recall_at_3']}", "semantic_quality")

    recommendations = get_json(base, "/v1/documents/doc-rollback/recommendations?limit=3")
    require(len(recommendations["results"]) == 3, "invalid recommendation count")
    require(all(item["id"] != "doc-rollback" for item in recommendations["results"]), "self recommendation")
    require(recommendations["index_version"] == meta["index_version"], "recommendation index mismatch")
    invalid = urllib.request.Request(base + "/v1/search", data=b'{"query":"  ","limit":3}',
                                     headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(invalid, timeout=5).close()
    except urllib.error.HTTPError as error:
        require(error.code == 422, "invalid input returned unexpected status")
    else:
        raise VerificationError("blank query was accepted")
    with urllib.request.urlopen(base + "/metrics", timeout=5) as response:
        metrics = response.read().decode()
    require("search_requests_total" in metrics and "search_index_loaded 1" in metrics, "metrics missing")
    (output / "metrics.prom").write_text(metrics, encoding="utf-8")
    save(output / "acceptance.json", {"status": "passed", "cases": len(cases), "quality": quality,
                                      "recommendations": recommendations, "invalid_input_status": 422})
    print(json.dumps({"meta": meta, "mrr": quality["mrr"], "hit_rate_at_3": quality["hit_rate_at_3"],
                      "macro_recall_at_3": quality["macro_recall_at_3"], "cases": len(cases)}))


def deployment(args):
    resource = json.loads(subprocess.check_output([
        "kubectl", "--request-timeout=15s", "-n", args.namespace, "get", "deployment",
        args.release + "-mlops-search", "-o", "json"], text=True, timeout=20))
    save(args.output / "deployment.json", resource)
    container = resource["spec"]["template"]["spec"]["containers"][0]
    if args.expected_digest:
        require(container["image"].endswith("@" + args.expected_digest), "Deployment digest mismatch")
    require(resource["status"].get("observedGeneration", 0) >= resource["metadata"]["generation"], "Deployment is not observed")
    require(resource["status"].get("updatedReplicas", 0) == resource["spec"]["replicas"] and
            resource["status"].get("availableReplicas", 0) >= resource["spec"]["replicas"], "Deployment is not available")


def main():
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--release")
    target.add_argument("--base-url")
    parser.add_argument("--namespace", default="mlops-students")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--output", type=Path, default=Path("evidence/smoke"))
    parser.add_argument("--expected-digest")
    parser.add_argument("--expected-environment")
    parser.add_argument("--expected-build-revision")
    parser.add_argument("--expected-index")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "failure.json").unlink(missing_ok=True)
    process = None
    try:
        if args.release:
            deployment(args)
            if args.port == 0:
                with socket.socket() as port:
                    port.bind(("127.0.0.1", 0))
                    args.port = port.getsockname()[1]
            with (args.output / "port-forward.log").open("w") as log:
                process = subprocess.Popen(["kubectl", "-n", args.namespace, "port-forward", "--address=127.0.0.1",
                    f"service/{args.release}-mlops-search", f"{args.port}:80"], stdout=log, stderr=subprocess.STDOUT)
        verify(args.base_url.rstrip("/") if args.base_url else f"http://127.0.0.1:{args.port}", args.output,
               args.expected_digest, args.expected_environment, args.expected_build_revision, args.expected_index, process)
    except Exception as error:
        save(args.output / "failure.json", {"kind": getattr(error, "kind", "transport"), "message": str(error)})
        raise
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
