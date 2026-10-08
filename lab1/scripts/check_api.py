import argparse
import json
import urllib.request
from pathlib import Path


def verify(client):
    health = client("GET", "/health")
    assert health == {"status": "ready", "model_version": "iris-v1"}, health
    samples = ([5.1, 3.5, 1.4, 0.2], [7.0, 3.2, 4.7, 1.4], [6.3, 3.3, 6.0, 2.5])
    predictions = []
    for expected, features in enumerate(samples):
        result = client("POST", "/predict", {"features": features})
        assert result == {"class_id": expected, "model_version": "iris-v1"}, result
        predictions.append({"features": features, **result})
    return {"health": health, "predictions": predictions}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--output", type=Path, default=Path("evidence/local-api.json"))
    args = parser.parse_args()
    if args.base_url:
        def client(method, path, body=None):
            request = urllib.request.Request(
                args.base_url.rstrip("/") + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"Content-Type": "application/json"}, method=method,
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.load(response)
        report = verify(client)
    else:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as api:
            def client(method, path, body=None):
                response = api.request(method, path, json=body)
                response.raise_for_status()
                return response.json()
            report = verify(client)
            assert api.post("/predict", json={"features": [1, 2]}).status_code == 422
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
