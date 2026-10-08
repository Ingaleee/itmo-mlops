"""Validate immutable images and preserved runtime protections in rendered manifests."""
import argparse
import json
import subprocess
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--helm", default="helm")
    args = parser.parse_args()
    digest = "sha256:" + "a" * 64
    command = [args.helm, "template", "esolovev-search-staging", "helm/mlops-search", "-n", "mlops-students"]
    for invalid in ("", "latest", "sha256:abc", "sha256:" + "g" * 64):
        result = subprocess.run(command + ["--set-string", "image.digest=" + invalid], capture_output=True, text=True)
        assert result.returncode != 0 and "digest" in result.stderr, result.stderr
    for repository in ("ghcr.io/ingaleee/esolovev-search:latest", "ghcr.io/ingaleee/esolovev-search@" + digest):
        result = subprocess.run(command + ["--set-string", "image.digest=" + digest, "--set-string", "image.repository=" + repository], capture_output=True, text=True)
        assert result.returncode != 0 and "repository" in result.stderr, result.stderr
    options = ["--set-string", "image.repository=ghcr.io/ingaleee/esolovev-search", "--set-string", "image.digest=" + digest]
    for key, value in (("rankingMode", "typo"), ("environment", "typo"), ("replicaCount", "0")):
        result = subprocess.run(command + options + ["--set", key + "=" + value], capture_output=True, text=True)
        assert result.returncode != 0, f"unsafe {key} accepted"
    subprocess.run([args.helm, "lint", "helm/mlops-search"] + options, check=True)
    rendered = subprocess.check_output(command + options, text=True)
    objects = list(yaml.safe_load_all(rendered))
    deployment = next(obj for obj in objects if obj["kind"] == "Deployment")
    service = next(obj for obj in objects if obj["kind"] == "Service")
    config = next(obj for obj in objects if obj["kind"] == "ConfigMap")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "ghcr.io/ingaleee/esolovev-search@" + digest
    assert container["readinessProbe"]["httpGet"]["path"] == "/readyz"
    assert container["livenessProbe"]["httpGet"]["path"] == "/livez"
    assert container["securityContext"]["readOnlyRootFilesystem"]
    pod = deployment["spec"]["template"]["spec"]
    assert pod["automountServiceAccountToken"] is False
    assert pod["securityContext"]["runAsUser"] == pod["securityContext"]["runAsGroup"] == 10001
    assert container["startupProbe"]["httpGet"]["path"] == "/readyz"
    assert container["resources"]["limits"] and container["resources"]["requests"]
    assert service["spec"]["type"] == "ClusterIP"
    assert config["data"]["IMAGE_DIGEST"] == digest
    assert any(obj["kind"] == "Pod" and obj["metadata"].get("annotations", {}).get("helm.sh/hook") == "test" for obj in objects)
    evidence = Path("evidence")
    evidence.mkdir(exist_ok=True)
    (evidence / "helm-render.yaml").write_text(rendered)
    (evidence / "helm-validation.json").write_text(json.dumps({"invalid_digests_rejected":4,"mutable_repositories_rejected":2,"runtime_contract":"passed"},indent=2)+"\n")
    print("Chart validation passed")


if __name__ == "__main__":
    main()
