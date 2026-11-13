"""Render/dry-run/apply namespaced workloads; secrets are supplied separately."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]


def resources(app_image, ollama_image, local=False, image_pull_secret=None):
    source = (ROOT / "deploy/base.yaml").read_text(encoding="utf-8")
    docs = list(
        yaml.safe_load_all(
            source.replace("APP_IMAGE", app_image).replace("OLLAMA_IMAGE", ollama_image)
        )
    )
    if image_pull_secret:
        for doc in docs:
            if doc["kind"] == "Deployment":
                doc["spec"]["template"]["spec"]["imagePullSecrets"] = [
                    {"name": image_pull_secret}
                ]
    if local:
        docs = [d for d in docs if d["kind"] != "PersistentVolumeClaim"]
        llm = next(
            d
            for d in docs
            if d["metadata"]["name"] == "llm-local" and d["kind"] == "Deployment"
        )
        pod = llm["spec"]["template"]["spec"]
        # Explicit isolated k3d mount: reuse downloaded public weights without
        # making another multi-gigabyte copy on a constrained workstation.
        pod["initContainers"] = pod["initContainers"][1:]
        pod["volumes"][0] = {
            "name": "models",
            "hostPath": {"path": "/models", "type": "Directory"},
        }
    config = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "knowledge-model-config"},
        "data": {"Modelfile": (ROOT / "model/Modelfile").read_text(encoding="utf-8")},
    }
    return [config, *docs]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kubeconfig", required=True)
    p.add_argument("--namespace", default="itmo-student-01")
    p.add_argument("--app-image", required=True)
    p.add_argument("--ollama-image", required=True)
    p.add_argument("--local", action="store_true")
    p.add_argument("--image-pull-secret")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if args.namespace != "itmo-student-01":
        raise SystemExit("Only the assigned teaching namespace/profile is supported")
    for image in (args.app_image, args.ollama_image):
        if not args.local and not re.fullmatch(
            r"[a-z0-9./_-]+@sha256:[0-9a-f]{64}", image
        ):
            raise SystemExit("Teaching images must be immutable SHA-256 references")
    command = ["kubectl", "--kubeconfig", args.kubeconfig, "-n", args.namespace]
    docs = resources(
        args.app_image, args.ollama_image, args.local, args.image_pull_secret
    )
    with tempfile.TemporaryDirectory(prefix="lab3-manifests-") as temporary:
        manifest = Path(temporary) / "workloads.yaml"
        manifest.write_text(
            yaml.safe_dump_all(docs, allow_unicode=True), encoding="utf-8"
        )
        subprocess.run(
            [*command, "apply", "--dry-run=server", "-f", str(manifest)], check=True
        )
        if args.apply:
            subprocess.run([*command, "apply", "-f", str(manifest)], check=True)
            for name in ("kb-mcp", "knowledge-portal", "llm-local"):
                subprocess.run(
                    [
                        *command,
                        "rollout",
                        "status",
                        "deployment/" + name,
                        "--timeout=10m",
                    ],
                    check=True,
                )
    print(
        json.dumps(
            {
                "namespace": args.namespace,
                "profile": "local-k3d" if args.local else "teaching",
                "result": "applied" if args.apply else "server-dry-run",
            }
        )
    )


if __name__ == "__main__":
    main()
