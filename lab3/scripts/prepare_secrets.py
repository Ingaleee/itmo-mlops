"""Install local files directly into the assigned namespace, without CI or Git."""

import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.corpus import inspect


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kubeconfig", required=True)
    p.add_argument("--corpus", required=True, type=Path)
    p.add_argument("--mcp-token", required=True, type=Path)
    p.add_argument("--portal-token", required=True, type=Path)
    p.add_argument("--cloud-key", type=Path)
    args = p.parse_args()
    corpus = args.corpus.read_bytes()
    inspect(corpus)

    def credential(path):
        value = path.read_text(encoding="utf-8-sig").strip()
        if len(value) < 24 or any(c.isspace() for c in value):
            raise ValueError("Credential file is invalid (content withheld)")
        return value.encode()

    secrets = {
        "knowledge-corpus": {"corpus.json": corpus},
        "knowledge-service": {
            "mcp-token": credential(args.mcp_token),
            "portal-token": credential(args.portal_token),
        },
    }
    if args.cloud_key:
        secrets["knowledge-cloud"] = {"api-key": credential(args.cloud_key)}
    # Server-side apply avoids a second plaintext copy in last-applied annotations.
    for name, values in secrets.items():
        resource = {
            "apiVersion": "v1",
            "kind": "Secret",
            "type": "Opaque",
            "metadata": {
                "name": name,
                "namespace": "itmo-student-01",
                "labels": {"app.kubernetes.io/part-of": "esolovev-knowledge"},
            },
            "data": {
                key: base64.b64encode(value).decode() for key, value in values.items()
            },
        }
        subprocess.run(
            [
                "kubectl",
                "--kubeconfig",
                args.kubeconfig,
                "-n",
                "itmo-student-01",
                "apply",
                "--server-side",
                "--field-manager=knowledge-local-setup",
                "-f",
                "-",
            ],
            input=json.dumps(resource).encode(),
            check=True,
        )
    print("Knowledge inputs installed directly; no secret contents logged")


if __name__ == "__main__":
    main()
