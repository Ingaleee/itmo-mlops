import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify(client):
    require(client("GET", "/live") == {"status": "alive"}, "liveness contract failed")
    health = client("GET", "/health")
    require(health == {"status": "ready", "model_version": "iris-v1"}, str(health))
    samples = ([5.1, 3.5, 1.4, 0.2], [7.0, 3.2, 4.7, 1.4], [6.3, 3.3, 6.0, 2.5])
    predictions = []
    for expected, features in enumerate(samples):
        result = client("POST", "/predict", {"features": features})
        require(result == {"class_id": expected, "model_version": "iris-v1"}, str(result))
        predictions.append({"features": features, **result})
    invalid = ([1, 2], [True, 2, 3, 4], [1e100, 2, 3, 4], [float("nan"), 2, 3, 4], [float("inf"), 2, 3, 4])
    for features in invalid:
        response = client("POST", "/predict", {"features": features}, expected_status=422)
        require(isinstance(response.get("detail"), list), "validation contract failed")
    return {"health": health, "predictions": predictions, "invalid_inputs_rejected": len(invalid)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--output", type=Path, default=Path("evidence/local-api.json"))
    args = parser.parse_args()
    if args.base_url:
        def client(method, path, body=None, expected_status=200):
            request = urllib.request.Request(
                args.base_url.rstrip("/") + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"Content-Type": "application/json"}, method=method,
            )
            try:
                response = urllib.request.urlopen(request, timeout=10)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                require(response.code == expected_status, f"{path}: expected {expected_status}, received {response.code}")
                return json.load(response)
        report = verify(client)
    else:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as api:
            def client(method, path, body=None, expected_status=200):
                response = api.request(method, path, content=json.dumps(body) if body is not None else None,
                                       headers={"Content-Type": "application/json"})
                require(response.status_code == expected_status, f"{path}: expected {expected_status}, received {response.status_code}")
                return response.json()
            report = verify(client)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
