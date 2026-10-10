"""Collect real local command output and HTTP responses for documentation.

Uses the active Python environment. Run from any directory; application processes
are bound to localhost and stopped when collection finishes.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/media/sources"
PROCESSES = []


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command(lab, name, arguments):
    run = subprocess.run([sys.executable, *arguments], cwd=ROOT / lab, capture_output=True,
                         text=True, encoding="utf-8", timeout=150,
                         env={**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"})
    report = {"working_directory": lab, "command": "python " + " ".join(arguments),
              "exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr}
    save(name, report)
    if run.returncode:
        raise RuntimeError(f"{lab}: {report['command']} failed; see {name}")
    print(f"PASS {lab}: {report['command']}", flush=True)
    return report


def start(lab, port, mode="normal"):
    log = (ROOT / ".course-access" / f"media-{lab}-{mode}.log").open("w", encoding="utf-8")
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                               "--port", str(port)], cwd=ROOT / lab, stdout=log, stderr=log,
                              env={**os.environ, "RANKING_MODE": mode, "ENVIRONMENT": "local",
                                   "PYTHONIOENCODING": "utf-8"})
    PROCESSES.append((process, log))
    endpoint = "/health" if lab == "lab1" else "/readyz"
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError(f"{lab} API exited")
        try:
            request(port, "GET", endpoint)
            return
        except (OSError, TimeoutError):
            time.sleep(.3)
    raise RuntimeError(f"{lab} API did not become ready")


def request(port, method, path, body=None, request_id=None):
    headers = {"Content-Type": "application/json"}
    if request_id:
        headers["X-Request-ID"] = request_id
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method, headers=headers,
                                 data=None if body is None else json.dumps(body).encode())
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        content = response.read().decode()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = content
        return {"method": method, "endpoint": path, "request": body, "status_code": response.code,
                "headers": {k.lower(): v for k, v in response.headers.items()
                            if k.lower() in ("content-type", "x-request-id", "x-response-time-ms")},
                "response": data}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        command("lab1", "iris-training.json", ["train.py"])
        command("lab1", "iris-tests.json", ["-m", "pytest", "-q"])
        command("lab2", "search-build.json", ["scripts/build_index.py", "--output", "artifacts"])
        command("lab2", "search-tests.json", ["-m", "pytest", "-q"])
        command("lab2", "search-quality.json", ["scripts/check_quality.py"])
        for mode in ("normal", "reverse"):
            save(f"search-quality-{mode}.json", json.loads((ROOT / f"lab2/evidence/quality-{mode}.json").read_text()))
        first = json.loads((ROOT / "lab2/artifacts/metadata.json").read_text())
        second_command = command("lab2", "search-rebuild.json", ["scripts/build_index.py", "--output", "evidence/media-rebuild"])
        second = json.loads(second_command["stdout"])
        same = first == second
        save("search-reproducibility.json", {"first": first, "second": second, "metadata_equal": same,
                                            "sha256_equal": first["artifact_sha256"] == second["artifact_sha256"]})
        if not same:
            raise RuntimeError("index rebuild is not reproducible")
        start("lab1", 8000)
        start("lab2", 8001)
        iris = {"health": request(8000, "GET", "/health"), "live": request(8000, "GET", "/live")}
        for key, features in (("setosa", [5.1,3.5,1.4,.2]), ("versicolor", [7,3.2,4.7,1.4]),
                              ("virginica", [6.3,3.3,6,2.5]), ("invalid-size", [1,2]),
                              ("invalid-type", [True,2,3,4])):
            iris[key] = request(8000, "POST", "/predict", {"features": features})
        save("iris-http.json", iris)
        save("iris-openapi.json", request(8000, "GET", "/openapi.json")["response"])
        command("lab1", "iris-external-api.json", ["scripts/check_api.py", "--base-url", "http://127.0.0.1:8000"])
        search = {"ready": request(8001, "GET", "/readyz"), "meta": request(8001, "GET", "/meta"),
                  "search": request(8001, "POST", "/v1/search",
                                    {"query": "как вернуть предыдущую модель после плохого релиза", "limit": 3}, "demo-search"),
                  "recommendations": request(8001, "GET", "/v1/documents/doc-rollback/recommendations?limit=3"),
                  "invalid": request(8001, "POST", "/v1/search", {"query": "  ", "limit": 3}),
                  "metrics": request(8001, "GET", "/metrics")}
        save("search-http.json", search)
        save("search-openapi.json", request(8001, "GET", "/openapi.json")["response"])
        command("lab2", "search-external-api.json", ["scripts/verify_release.py", "--base-url", "http://127.0.0.1:8001",
                                                        "--output", "evidence/media-local"])
        import joblib
        from sklearn.datasets import load_iris
        model = joblib.load(ROOT / "lab1/model.joblib")
        data = load_iris()
        save("iris-model.json", {"estimator": type(model).__name__, "n_estimators": model.n_estimators,
                                 "random_state": model.random_state, "samples": len(data.data),
                                 "features": list(data.feature_names), "classes": list(data.target_names),
                                 "artifact_sha256": hashlib.sha256((ROOT / "lab1/model.joblib").read_bytes()).hexdigest(),
                                 "artifact_bytes": (ROOT / "lab1/model.joblib").stat().st_size})
        print("Local evidence collection complete", flush=True)
    finally:
        for process, log in PROCESSES:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            log.close()


if __name__ == "__main__":
    main()
